import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.check_document import check_document
from backend.hybrid_result import combine_results
from backend.profiles.rop.payload_builder import build_rop_rule_facts
from backend.profiles.rop.rop_control import run_rop_control
from backend.profiles.rop.rop_structure import extract_rop_structure
from tests.helpers import add_paragraph

BASE_DIR = Path(__file__).resolve().parent.parent

ROP_NORMATIVE_PROFILE = json.loads(
    (BASE_DIR / "backend" / "profiles" / "rop" / "rules_rop.json").read_text(
        encoding="utf-8"
    )
)


def make_rop_document(
    annotation: str | None = "Краткая аннотация.",
    contents: str | None = "1. Общие сведения о программе 1",
    messages: str | None = None,
) -> dict:
    blocks = []

    if annotation is not None:
        add_paragraph(blocks, "Аннотация", "Heading 1")

        if annotation:
            add_paragraph(blocks, annotation)

    if contents is not None:
        add_paragraph(blocks, "Содержание", "toc 1")

        if contents:
            add_paragraph(blocks, contents, "toc 1")

    add_paragraph(blocks, "Общие сведения о программе", "Heading 1")
    add_paragraph(blocks, "Назначение программы", "Heading 2")
    add_paragraph(blocks, "Программа предназначена для проверки устройства.")
    add_paragraph(blocks, "Программа выполняет приём и обработку данных.")

    add_paragraph(blocks, "Условия выполнения программы", "Heading 1")
    add_paragraph(blocks, "Требуются персональный компьютер и ОС Windows.")

    add_paragraph(blocks, "Выполнение программы", "Heading 1")
    add_paragraph(
        blocks,
        "Оператор запускает программу, задаёт параметры "
        "и завершает работу закрытием формы.",
    )

    if messages is not None:
        add_paragraph(blocks, "Сообщения оператору", "Heading 1")

        if messages:
            add_paragraph(blocks, messages)

    return {
        "blocks": blocks,
    }


class RopTests(unittest.TestCase):
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
        statuses = {check["rule_id"]: check["status"] for check in control["checks"]}

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

                checks = {check["rule_id"]: check for check in result["checks"]}

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
        checks = {check["rule_id"]: check for check in result["checks"]}

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
                    "status": ("fail" if number == 1 else "pass"),
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
            check for check in final_result["checks"] if check["rule_id"] == "ROP-03"
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
                profile_id="rop",
            )

        self.assertEqual(mocked_request.call_count, 6)
        self.assertEqual(usage["request_count"], 6)
        self.assertEqual(usage["prompt_tokens"], 60)
        self.assertEqual(usage["completion_tokens"], 30)
        self.assertEqual(usage["total_tokens"], 90)

        self.assertEqual(
            [check["rule_id"] for check in result["checks"]],
            [f"ROP-{number:02d}" for number in range(1, 7)],
        )


if __name__ == "__main__":
    unittest.main()
