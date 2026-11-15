import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.check_document import check_document
from backend.docx_reader import read_docx
from backend.hybrid_result import build_summary, combine_results
from backend.profiles.ved.control_checker import run_structural_control
from backend.profiles.ved.fact_extractor import extract_document_facts
from backend.result_validator import validate_result
from backend.schema_builder import build_result_schema
from tests.create_samples import main as create_samples

BASE_DIR = Path(__file__).resolve().parent.parent
VALID_SAMPLE = BASE_DIR / "samples" / "ведомость_основная.docx"
INVALID_SAMPLE = BASE_DIR / "samples" / "ведомость_с_ошибкой.docx"
NORMATIVE_PROFILE = json.loads(
    (BASE_DIR / "backend" / "profiles" / "ved" / "rules_ved.json").read_text(
        encoding="utf-8"
    )
)


def make_ai_result(document_structure: dict) -> dict:
    facts = extract_document_facts(document_structure)
    header_evidence = [item["evidence_id"] for item in facts["first_table_headers"]]
    designation_evidence = [
        item["evidence_id"] for item in facts["document_designations"]
    ]

    evidence_by_rule = {
        "VED-01": ["P4"],
        "VED-02": ["P3"],
        "VED-03": header_evidence,
        "VED-04": header_evidence,
        "VED-05": ["P4"],
        "VED-06": designation_evidence,
    }

    return {
        "checks": [
            {
                "rule_id": f"VED-{number:02d}",
                "observation": "Тестовое наблюдение.",
                "status": "pass",
                "comment": "Тестовый комментарий ИИ.",
                "evidence": evidence_by_rule[f"VED-{number:02d}"],
            }
            for number in range(1, 7)
        ],
    }


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_samples()
        cls.valid_document = read_docx(VALID_SAMPLE)
        cls.invalid_document = read_docx(INVALID_SAMPLE)

    def test_fact_extraction_uses_document_kind_codes(self):
        facts = extract_document_facts(self.valid_document)
        codes = [item["document_kind_code"] for item in facts["document_designations"]]
        self.assertEqual(codes, ["31", "32"])

    def test_valid_sample_control(self):
        result = run_structural_control(self.valid_document)
        statuses = {check["rule_id"]: check["status"] for check in result["checks"]}
        self.assertEqual(
            statuses,
            {
                "VED-01": "pass",
                "VED-03": "pass",
                "VED-04": "pass",
                "VED-05": "pass",
                "VED-06": "pass",
            },
        )

    def test_invalid_sample_control(self):
        result = run_structural_control(self.invalid_document)
        statuses = {check["rule_id"]: check["status"] for check in result["checks"]}
        self.assertEqual(statuses["VED-03"], "fail")
        self.assertEqual(statuses["VED-04"], "review")
        self.assertEqual(statuses["VED-06"], "pass")

    def test_disagreement_becomes_review_without_changing_ai_result(self):
        ai_result = make_ai_result(self.invalid_document)
        validate_result(
            ai_result,
            self.invalid_document,
            NORMATIVE_PROFILE,
        )
        original_ai_result = copy.deepcopy(ai_result)

        final_result = combine_results(
            ai_result,
            self.invalid_document,
            NORMATIVE_PROFILE,
        )
        ved03 = next(
            check for check in final_result["checks"] if check["rule_id"] == "VED-03"
        )

        self.assertEqual(
            final_result["document_type"],
            NORMATIVE_PROFILE["document_type"],
        )
        self.assertEqual(
            final_result["standard"],
            NORMATIVE_PROFILE["standard"],
        )
        self.assertEqual(ved03["status"], "review")
        self.assertFalse(ved03["agreement"])
        self.assertEqual(ved03["ai"]["status"], "pass")
        self.assertEqual(ved03["control"]["status"], "fail")
        self.assertEqual(ai_result, original_ai_result)

    def test_unknown_evidence_is_rejected(self):
        ai_result = make_ai_result(self.valid_document)
        ai_result["checks"][0]["evidence"] = ["T999"]
        with self.assertRaises(ValueError):
            validate_result(
                ai_result,
                self.valid_document,
                NORMATIVE_PROFILE,
            )

    def test_ved_check_uses_single_ai_request(self):
        def fake_request(payload):
            schema = payload["response_format"]["json_schema"]["schema"]
            checks_schema = schema["properties"]["checks"]

            self.assertEqual(checks_schema["minItems"], 6)
            self.assertEqual(checks_schema["maxItems"], 6)

            user_content = json.loads(payload["messages"][1]["content"])

            self.assertIn("normative_profile", user_content)
            self.assertIn("document_facts", user_content)
            self.assertIn("rule_facts", user_content)
            self.assertIn("document", user_content)

            return make_ai_result(self.valid_document), {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }

        with (
            patch(
                "backend.check_document.read_docx",
                return_value=self.valid_document,
            ),
            patch(
                "backend.check_document.request_ai_result",
                side_effect=fake_request,
            ) as mocked_request,
        ):
            result, usage = check_document(
                "unused.docx",
                save_outputs=False,
                profile_id="ved",
            )

        self.assertEqual(mocked_request.call_count, 1)

        self.assertEqual(
            [check["rule_id"] for check in result["checks"]],
            [f"VED-{number:02d}" for number in range(1, 7)],
        )

        self.assertEqual(
            [check["status"] for check in result["checks"]],
            ["pass"] * 6,
        )

        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["completion_tokens"], 5)
        self.assertEqual(usage["total_tokens"], 15)

    def test_self_included_statement_fails_ved05(self):
        document_structure = read_docx(VALID_SAMPLE)

        changed_evidence_id = None

        # Меняем код первого документа с 31 на 20,
        # имитируя самовключение текущей ведомости.
        for block in document_structure.get("blocks", []):
            if block.get("type") != "table":
                continue

            for row in block.get("rows", []):
                if isinstance(row, dict):
                    cells = row.get("cells", [])
                else:
                    cells = row

                for cell in cells:
                    text = cell.get("text", "")

                    if " 31 01" in text:
                        cell["text"] = text.replace(
                            " 31 01",
                            " 20 01",
                        )
                        changed_evidence_id = cell["id"]

        self.assertIsNotNone(changed_evidence_id)

        control_result = run_structural_control(document_structure)

        control_by_id = {check["rule_id"]: check for check in control_result["checks"]}

        ved_05 = control_by_id["VED-05"]

        self.assertEqual(ved_05["status"], "fail")
        self.assertIn(
            changed_evidence_id,
            ved_05["evidence"],
        )

    def test_result_schema_uses_active_profile(self):
        profile = {
            "rules": [
                {"id": "TEST-01"},
                {"id": "TEST-02"},
            ]
        }

        schema = build_result_schema(profile)
        checks_schema = schema["properties"]["checks"]

        self.assertEqual(checks_schema["minItems"], 2)
        self.assertEqual(checks_schema["maxItems"], 2)
        self.assertEqual(
            checks_schema["items"]["properties"]["rule_id"]["enum"],
            ["TEST-01", "TEST-02"],
        )

    def test_summary_uses_active_profile(self):
        profile = {
            "standard": "ТЕСТОВЫЙ-СТАНДАРТ",
        }
        checks = [
            {
                "status": "pass",
                "control": {"status": "pass"},
            },
            {
                "status": "review",
                "control": None,
            },
        ]

        summary = build_summary(checks, profile)

        self.assertIn(
            "по ТЕСТОВЫЙ-СТАНДАРТ: 2.",
            summary,
        )
        self.assertIn("pass — 1", summary)
        self.assertIn("fail — 0", summary)
        self.assertIn("review — 1", summary)
        self.assertIn(
            "для 1 из 2 правил",
            summary,
        )
        self.assertNotIn("шесть", summary)


if __name__ == "__main__":
    unittest.main()
