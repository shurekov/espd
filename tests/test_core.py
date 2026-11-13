import copy
import unittest
import json

from pathlib import Path
from backend.profiles.ved.control_checker import run_structural_control
from tests.create_samples import main as create_samples
from backend.docx_reader import read_docx
from backend.profiles.ved.fact_extractor import extract_document_facts
from backend.hybrid_result import build_summary, combine_results
from backend.result_validator import validate_result
from backend.schema_builder import build_result_schema
from backend.profiles.rsp.rsp_control import run_rsp_control
from backend.profiles.rsp.payload_builder import build_rsp_rule_facts
from backend.profiles.rsp.rsp_structure import extract_rsp_structure
from backend.profiles.rop.payload_builder import build_rop_rule_facts
from backend.profiles.rop.rop_control import run_rop_control
from backend.profiles.rop.rop_structure import extract_rop_structure
from unittest.mock import patch
from backend.check_document import check_document


BASE_DIR = Path(__file__).resolve().parent.parent
VALID_SAMPLE = BASE_DIR / "samples" / "ведомость_основная.docx"
INVALID_SAMPLE = BASE_DIR / "samples" / "ведомость_с_ошибкой.docx"
NORMATIVE_PROFILE = json.loads(
    (
            BASE_DIR
            / "backend"
            / "profiles"
            / "ved"
            / "rules_ved.json"
    ).read_text(encoding="utf-8")
)

RSP_NORMATIVE_PROFILE = json.loads(
    (
            BASE_DIR
            / "backend"
            / "profiles"
            / "rsp"
            / "rules_rsp.json"
    ).read_text(encoding="utf-8")
)

ROP_NORMATIVE_PROFILE = json.loads(
    (
            BASE_DIR
            / "backend"
            / "profiles"
            / "rop"
            / "rules_rop.json"
    ).read_text(encoding="utf-8")
)

def make_ai_result(document_structure: dict) -> dict:
    facts = extract_document_facts(document_structure)
    header_evidence = [
        item["evidence_id"]
        for item in facts["first_table_headers"]
    ]
    designation_evidence = [
        item["evidence_id"]
        for item in facts["document_designations"]
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

def make_rsp_document(
        annotation: str | None = "Краткая аннотация.",
        contents: str | None = "1. Общие сведения о программе 1",
        duplicate_annotation: bool = False,
) -> dict:
    blocks = []
    paragraph_number = 0

    def add_paragraph(
            text: str,
            style: str = "Normal",
    ) -> None:
        nonlocal paragraph_number

        paragraph_number += 1
        blocks.append({
            "id": f"P{paragraph_number}",
            "type": "paragraph",
            "style": style,
            "text": text,
        })

    if annotation is not None:
        add_paragraph("Аннотация", "Heading 1")

        if annotation:
            add_paragraph(annotation)

    if duplicate_annotation:
        add_paragraph("Аннотация", "Heading 1")
        add_paragraph("Вторая аннотация.")

    if contents is not None:
        add_paragraph("Содержание", "toc 1")

        if contents:
            add_paragraph(contents, "toc 1")

    add_paragraph("Общие сведения о программе", "Heading 1")
    add_paragraph("Назначение и функции программы.")

    return {
        "blocks": blocks,
    }

def make_rop_document(
        annotation: str | None = "Краткая аннотация.",
        contents: str | None = "1. Общие сведения о программе 1",
        messages: str | None = None,
) -> dict:
    blocks = []
    paragraph_number = 0

    def add_paragraph(
            text: str,
            style: str = "Normal",
    ) -> None:
        nonlocal paragraph_number

        paragraph_number += 1
        blocks.append({
            "id": f"P{paragraph_number}",
            "type": "paragraph",
            "style": style,
            "text": text,
        })

    if annotation is not None:
        add_paragraph("Аннотация", "Heading 1")

        if annotation:
            add_paragraph(annotation)

    if contents is not None:
        add_paragraph("Содержание", "toc 1")

        if contents:
            add_paragraph(contents, "toc 1")

    add_paragraph("Общие сведения о программе", "Heading 1")
    add_paragraph("Назначение программы", "Heading 2")
    add_paragraph("Программа предназначена для проверки устройства.")
    add_paragraph("Программа выполняет приём и обработку данных.")

    add_paragraph("Условия выполнения программы", "Heading 1")
    add_paragraph("Требуются персональный компьютер и ОС Windows.")

    add_paragraph("Выполнение программы", "Heading 1")
    add_paragraph(
        "Оператор запускает программу, задаёт параметры "
        "и завершает работу закрытием формы."
    )

    if messages is not None:
        add_paragraph("Сообщения оператору", "Heading 1")

        if messages:
            add_paragraph(messages)

    return {
        "blocks": blocks,
    }

class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_samples()
        cls.valid_document = read_docx(VALID_SAMPLE)
        cls.invalid_document = read_docx(INVALID_SAMPLE)

    def test_fact_extraction_uses_document_kind_codes(self):
        facts = extract_document_facts(self.valid_document)
        codes = [
            item["document_kind_code"]
            for item in facts["document_designations"]
        ]
        self.assertEqual(codes, ["31", "32"])

    def test_valid_sample_control(self):
        result = run_structural_control(self.valid_document)
        statuses = {
            check["rule_id"]: check["status"]
            for check in result["checks"]
        }
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
        statuses = {
            check["rule_id"]: check["status"]
            for check in result["checks"]
        }
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
            check
            for check in final_result["checks"]
            if check["rule_id"] == "VED-03"
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

    def test_self_included_statement_fails_ved05(self):
        document_structure = read_docx(
            "samples/ведомость_основная.docx"
        )

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

        control_result = run_structural_control(
            document_structure
        )

        control_by_id = {
            check["rule_id"]: check
            for check in control_result["checks"]
        }

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

    def test_rsp_present_information_parts_pass(self):
        document = make_rsp_document()

        result = run_rsp_control(document)
        statuses = {
            check["rule_id"]: check["status"]
            for check in result["checks"]
        }

        self.assertEqual(statuses["RSP-01"], "pass")
        self.assertEqual(statuses["RSP-02"], "pass")

    def test_rsp_missing_annotation_fails(self):
        document = make_rsp_document(annotation=None)

        result = run_rsp_control(document)
        statuses = {
            check["rule_id"]: check["status"]
            for check in result["checks"]
        }

        self.assertEqual(statuses["RSP-01"], "fail")
        self.assertEqual(statuses["RSP-02"], "pass")

    def test_rsp_empty_information_parts_fail(self):
        document = make_rsp_document(
            annotation="",
            contents="",
        )

        result = run_rsp_control(document)
        statuses = {
            check["rule_id"]: check["status"]
            for check in result["checks"]
        }

        self.assertEqual(statuses["RSP-01"], "fail")
        self.assertEqual(statuses["RSP-02"], "fail")

    def test_rsp_ambiguous_annotation_requires_review(self):
        document = make_rsp_document(
            duplicate_annotation=True,
        )

        result = run_rsp_control(document)
        statuses = {
            check["rule_id"]: check["status"]
            for check in result["checks"]
        }

        self.assertEqual(statuses["RSP-01"], "review")
        self.assertEqual(statuses["RSP-02"], "pass")

    def test_rsp_section_matching_is_not_a_verdict(self):
        document = make_rsp_document()
        rsp_structure = extract_rsp_structure(document)

        rule_facts = build_rsp_rule_facts(rsp_structure)
        candidates = rule_facts["section_candidates"]

        self.assertEqual(
            candidates["RSP-03"]["match_status"],
            "found",
        )
        self.assertEqual(
            candidates["RSP-04"]["match_status"],
            "not_found",
        )

        # not_found означает только отсутствие точного кандидата,
        # а не итоговый fail по правилу.
        self.assertNotIn("status", candidates["RSP-04"])

        self.assertTrue(
            rule_facts["information_parts"]["RSP-01"]["has_content"]
        )
        self.assertTrue(
            rule_facts["information_parts"]["RSP-02"]["has_content"]
        )

    def test_rsp_control_disagreement_becomes_review(self):
        document = make_rsp_document()

        ai_result = {
            "checks": [
                {
                    "rule_id": f"RSP-{number:02d}",
                    "observation": "Тестовое наблюдение.",
                    "status": (
                        "fail" if number == 1 else "pass"
                    ),
                    "comment": "Тестовый комментарий ИИ.",
                    "evidence": [],
                }
                for number in range(1, 9)
            ]
        }

        final_result = combine_results(
            ai_result,
            document,
            RSP_NORMATIVE_PROFILE,
        )

        rsp01 = final_result["checks"][0]
        rsp03 = next(
            check
            for check in final_result["checks"]
            if check["rule_id"] == "RSP-03"
        )

        # Python обнаружил непустую аннотацию, а ИИ ошибочно дал fail.
        self.assertEqual(rsp01["status"], "review")
        self.assertFalse(rsp01["agreement"])
        self.assertEqual(rsp01["ai"]["status"], "fail")
        self.assertEqual(rsp01["control"]["status"], "pass")

        # Содержательные разделы пока не имеют программного вердикта.
        self.assertIsNone(rsp03["control"])
        self.assertIsNone(rsp03["agreement"])
        self.assertEqual(rsp03["status"], "pass")

        self.assertEqual(
            final_result["document_type"],
            "Руководство системного программиста",
        )

    def test_rsp_check_uses_eight_isolated_ai_requests(self):
        document = make_rsp_document()

        def fake_request(payload):
            schema = payload["response_format"]["json_schema"]["schema"]
            check_schema = schema["properties"]["checks"]["items"]
            rule_id = check_schema["properties"]["rule_id"]["enum"][0]

            self.assertEqual(
                schema["properties"]["checks"]["minItems"],
                1,
            )
            self.assertEqual(
                schema["properties"]["checks"]["maxItems"],
                1,
            )

            user_content = json.loads(
                payload["messages"][1]["content"]
            )

            self.assertEqual(user_content["rule"]["id"], rule_id)
            self.assertNotIn("normative_profile", user_content)
            self.assertIn(
                rule_id,
                payload["messages"][0]["content"],
            )

            return {
                "checks": [
                    {
                        "rule_id": rule_id,
                        "observation": "Тестовое наблюдение.",
                        "status": "review",
                        "comment": "Тестовый комментарий.",
                        "evidence": [],
                    }
                ]
            }, {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }

        with patch(
                "backend.check_document.read_docx",
                return_value=document,
        ):
            with patch(
                    "backend.check_document.request_ai_result",
                    side_effect=fake_request,
            ) as mocked_request:
                result, usage = check_document(
                    "unused.docx",
                    save_outputs=False,
                    profile_id="rsp",
                )

        self.assertEqual(mocked_request.call_count, 8)
        self.assertEqual(usage["request_count"], 8)
        self.assertEqual(usage["prompt_tokens"], 80)
        self.assertEqual(usage["completion_tokens"], 40)
        self.assertEqual(usage["total_tokens"], 120)

        self.assertEqual(
            [
                check["rule_id"]
                for check in result["checks"]
            ],
            [
                f"RSP-{number:02d}"
                for number in range(1, 9)
            ],
        )
    def test_rsp_messages_control(self):
        cases = (
                (
                    "Программа не выдаёт сообщений.",
                    "pass",
                ),
                (
                    "В процессе работы программа может выдавать "
                    "информационные сообщения и сообщения об ошибках. "
                    "Оба типа сообщений содержат исчерпывающую информацию "
                    "о типе события или ошибке и причине их возникновения.",
                    "fail",
                ),
            )

        for text, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                document = make_rsp_document()
                document["blocks"].extend([
                    {
                        "id": "P7",
                        "type": "paragraph",
                        "style": "Heading 1",
                        "text": "Сообщения системному программисту",
                    },
                    {
                        "id": "P8",
                        "type": "paragraph",
                        "style": "Normal",
                        "text": text,
                    },
                ])

                result = run_rsp_control(document)
                checks = {
                    check["rule_id"]: check
                    for check in result["checks"]
                }

                self.assertEqual(
                    checks["RSP-08"]["status"],
                    expected_status,
                )

    def test_rsp_contents_accepts_oglavlenie_heading(self):
        document = make_rsp_document()

        for block in document["blocks"]:
            if block.get("text") == "Содержание":
                block["text"] = "Оглавление"

        result = run_rsp_control(document)
        checks = {
            check["rule_id"]: check
            for check in result["checks"]
        }

        self.assertEqual(checks["RSP-02"]["status"], "pass")
        self.assertEqual(
            checks["RSP-02"]["evidence"],
            ["P3", "P4"],
        )

    def test_rop_information_parts_and_section_matching(self):
        document = make_rop_document()
        rop_structure = extract_rop_structure(document)
        rule_facts = build_rop_rule_facts(rop_structure)

        candidates = rule_facts["section_candidates"]

        self.assertEqual(
            candidates["ROP-03"]["match_status"],
            "found",
        )
        self.assertEqual(
            candidates["ROP-03"]["headings"],
            ["Общие сведения о программе"],
        )

        for rule_id in ("ROP-04", "ROP-05"):
            self.assertEqual(
                candidates[rule_id]["match_status"],
                "found",
            )

        self.assertEqual(
            candidates["ROP-06"]["match_status"],
            "not_found",
        )
        self.assertNotIn("status", candidates["ROP-06"])

        control = run_rop_control(document)
        statuses = {
            check["rule_id"]: check["status"]
            for check in control["checks"]
        }

        self.assertEqual(statuses["ROP-01"], "pass")
        self.assertEqual(statuses["ROP-02"], "pass")
        self.assertEqual(statuses["ROP-06"], "review")

    def test_rop_messages_control(self):
        cases = (
            (
                "Программа не имеет пользовательского интерфейса, "
                "сообщения оператору не выдаются.",
                "pass",
            ),
            (
                "В процессе работы программа может выдавать "
                "информационные сообщения и сообщения об ошибках. "
                "Оба типа сообщений содержат исчерпывающую информацию "
                "о типе события или ошибке.",
                "fail",
            ),
            (
                "",
                "fail",
            ),
        )

        for text, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                document = make_rop_document(messages=text)
                result = run_rop_control(document)

                checks = {
                    check["rule_id"]: check
                    for check in result["checks"]
                }

                self.assertEqual(
                    checks["ROP-06"]["status"],
                    expected_status,
                )

    def test_rop_contents_accepts_oglavlenie_heading(self):
        document = make_rop_document()

        for block in document["blocks"]:
            if block.get("text") == "Содержание":
                block["text"] = "Оглавление"

        result = run_rop_control(document)
        checks = {
            check["rule_id"]: check
            for check in result["checks"]
        }

        self.assertEqual(checks["ROP-02"]["status"], "pass")
        self.assertEqual(
            checks["ROP-02"]["evidence"],
            ["P3", "P4"],
        )

    def test_rop_control_disagreement_becomes_review(self):
        document = make_rop_document()

        ai_result = {
            "checks": [
                {
                    "rule_id": f"ROP-{number:02d}",
                    "observation": "Тестовое наблюдение.",
                    "status": (
                        "fail" if number == 1 else "pass"
                    ),
                    "comment": "Тестовый комментарий ИИ.",
                    "evidence": [],
                }
                for number in range(1, 7)
            ]
        }

        original_ai_result = copy.deepcopy(ai_result)

        final_result = combine_results(
            ai_result,
            document,
            ROP_NORMATIVE_PROFILE,
        )

        rop01 = final_result["checks"][0]
        rop03 = next(
            check
            for check in final_result["checks"]
            if check["rule_id"] == "ROP-03"
        )

        self.assertEqual(rop01["status"], "review")
        self.assertFalse(rop01["agreement"])
        self.assertEqual(rop01["ai"]["status"], "fail")
        self.assertEqual(rop01["control"]["status"], "pass")

        self.assertIsNone(rop03["control"])
        self.assertIsNone(rop03["agreement"])
        self.assertEqual(rop03["status"], "pass")

        self.assertEqual(ai_result, original_ai_result)
        self.assertEqual(
            final_result["document_type"],
            "Руководство оператора",
        )

    def test_rop_check_uses_six_isolated_ai_requests(self):
        document = make_rop_document()

        def fake_request(payload):
            schema = payload["response_format"]["json_schema"]["schema"]
            check_schema = schema["properties"]["checks"]["items"]
            rule_id = check_schema["properties"]["rule_id"]["enum"][0]

            self.assertEqual(
                schema["properties"]["checks"]["minItems"],
                1,
            )
            self.assertEqual(
                schema["properties"]["checks"]["maxItems"],
                1,
            )

            user_content = json.loads(
                payload["messages"][1]["content"]
            )

            self.assertEqual(user_content["rule"]["id"], rule_id)
            self.assertNotIn("normative_profile", user_content)
            self.assertIn(
                rule_id,
                payload["messages"][0]["content"],
            )

            return {
                "checks": [
                    {
                        "rule_id": rule_id,
                        "observation": "Тестовое наблюдение.",
                        "status": "review",
                        "comment": "Тестовый комментарий.",
                        "evidence": [],
                    }
                ]
            }, {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }

        with patch(
                "backend.check_document.read_docx",
                return_value=document,
        ):
            with patch(
                    "backend.check_document.request_ai_result",
                    side_effect=fake_request,
            ) as mocked_request:
                result, usage = check_document(
                    "unused.docx",
                    save_outputs=False,
                    profile_id="rop",
                )

        self.assertEqual(mocked_request.call_count, 6)
        self.assertEqual(usage["request_count"], 6)
        self.assertEqual(usage["prompt_tokens"], 60)
        self.assertEqual(usage["completion_tokens"], 30)
        self.assertEqual(usage["total_tokens"], 90)

        self.assertEqual(
            [
                check["rule_id"]
                for check in result["checks"]
            ],
            [
                f"ROP-{number:02d}"
                for number in range(1, 7)
            ],
        )



if __name__ == "__main__":
    unittest.main()
