import json
import unittest
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.check_document import check_document
from backend.hybrid_result import combine_results
from backend.profiles.rsp.payload_builder import build_rsp_rule_facts
from backend.profiles.rsp.rsp_control import run_rsp_control
from backend.profiles.rsp.rsp_structure import extract_rsp_structure
from backend.profile_registry import get_profile
from tests.helpers import add_paragraph

BASE_DIR = Path(__file__).resolve().parent.parent

RSP_NORMATIVE_PROFILE = json.loads(
    (BASE_DIR / "backend" / "profiles" / "rsp" / "rules_rsp.json").read_text(
        encoding="utf-8"
    )
)


def make_rsp_document(
    annotation: str | None = "Краткая аннотация.",
    contents: str | None = "1. Общие сведения о программе 1",
    duplicate_annotation: bool = False,
) -> dict:
    blocks = []

    if annotation is not None:
        add_paragraph(blocks, "Аннотация", "Heading 1")

        if annotation:
            add_paragraph(blocks, annotation)

    if duplicate_annotation:
        add_paragraph(blocks, "Аннотация", "Heading 1")
        add_paragraph(blocks, "Вторая аннотация.")

    if contents is not None:
        add_paragraph(blocks, "Содержание", "toc 1")

        if contents:
            add_paragraph(blocks, contents, "toc 1")

    add_paragraph(blocks, "Общие сведения о программе", "Heading 1")
    add_paragraph(blocks, "Назначение и функции программы.")

    return {"blocks": blocks}


class RspTests(unittest.TestCase):
    def test_rsp_present_information_parts_pass(self):
        document = make_rsp_document()

        result = run_rsp_control(document)
        statuses = {check["rule_id"]: check["status"] for check in result["checks"]}

        self.assertEqual(statuses["RSP-01"], "pass")
        self.assertEqual(statuses["RSP-02"], "pass")

    def test_rsp_missing_annotation_fails(self):
        document = make_rsp_document(annotation=None)

        result = run_rsp_control(document)
        statuses = {check["rule_id"]: check["status"] for check in result["checks"]}

        self.assertEqual(statuses["RSP-01"], "fail")
        self.assertEqual(statuses["RSP-02"], "pass")

    def test_rsp_empty_information_parts_fail(self):
        document = make_rsp_document(
            annotation="",
            contents="",
        )

        result = run_rsp_control(document)
        statuses = {check["rule_id"]: check["status"] for check in result["checks"]}

        self.assertEqual(statuses["RSP-01"], "fail")
        self.assertEqual(statuses["RSP-02"], "fail")

    def test_rsp_ambiguous_annotation_requires_review(self):
        document = make_rsp_document(
            duplicate_annotation=True,
        )

        result = run_rsp_control(document)
        statuses = {check["rule_id"]: check["status"] for check in result["checks"]}

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

        self.assertTrue(rule_facts["information_parts"]["RSP-01"]["has_content"])
        self.assertTrue(rule_facts["information_parts"]["RSP-02"]["has_content"])

    def test_rsp_control_disagreement_becomes_review(self):
        document = make_rsp_document()

        ai_result = {
            "checks": [
                {
                    "rule_id": f"RSP-{number:02d}",
                    "observation": "Тестовое наблюдение.",
                    "status": ("fail" if number == 1 else "pass"),
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
            check for check in final_result["checks"] if check["rule_id"] == "RSP-03"
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
        profile = replace(get_profile("rsp"), max_tokens=450)

        def fake_request(payload):
            self.assertEqual(payload["max_tokens"], 450)
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

            user_content = json.loads(payload["messages"][1]["content"])

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

        with (
            patch(
                "backend.check_document.get_profile",
                return_value=profile,
            ),
            patch(
                "backend.check_document.read_docx",
                return_value=document,
            ),
            patch(
                "backend.check_document.request_ai_result",
                side_effect=fake_request,
            ) as mocked_request,
        ):
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
            [check["rule_id"] for check in result["checks"]],
            [f"RSP-{number:02d}" for number in range(1, 9)],
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
                document["blocks"].extend(
                    [
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
                    ]
                )

                result = run_rsp_control(document)
                checks = {check["rule_id"]: check for check in result["checks"]}

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
        checks = {check["rule_id"]: check for check in result["checks"]}

        self.assertEqual(checks["RSP-02"]["status"], "pass")
        self.assertEqual(
            checks["RSP-02"]["evidence"],
            ["P3", "P4"],
        )

    def test_combine_results_reuses_provided_profile_structure(self):
        document = make_rsp_document()

        rsp_structure = extract_rsp_structure(document)

        ai_result = {
            "checks": [
                {
                    "rule_id": f"RSP-{number:02d}",
                    "observation": "Тестовое наблюдение.",
                    "status": "pass",
                    "comment": "Тестовый комментарий ИИ.",
                    "evidence": [],
                }
                for number in range(1, 9)
            ]
        }

        profile = SimpleNamespace(
            extract_structure=Mock(
                side_effect=AssertionError("Extractor не должен вызываться повторно")
            ),
            run_control=Mock(return_value={"checks": []}),
            controlled_rules=frozenset(),
            build_diagnostics=lambda _document_structure, structure: {
                "structure": structure,
            },
        )

        with patch(
            "backend.hybrid_result.get_profile",
            return_value=profile,
        ):
            result = combine_results(
                ai_result,
                document,
                RSP_NORMATIVE_PROFILE,
                profile_structure=rsp_structure,
            )

        profile.extract_structure.assert_not_called()
        profile.run_control.assert_called_once_with(
            document,
            rsp_structure,
        )

        self.assertIs(
            result["diagnostics"]["structure"],
            rsp_structure,
        )


if __name__ == "__main__":
    unittest.main()
