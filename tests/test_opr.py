import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.check_document import check_document
from backend.hybrid_result import combine_results
from backend.profiles.opr.opr_control import run_opr_control
from backend.profiles.opr.opr_structure import extract_opr_structure
from backend.profiles.opr.payload_builder import build_opr_rule_facts


BASE_DIR = Path(__file__).resolve().parent.parent

OPR_NORMATIVE_PROFILE = json.loads(
    (
            BASE_DIR
            / "backend"
            / "profiles"
            / "opr"
            / "rules_opr.json"
    ).read_text(encoding="utf-8")
)


def make_opr_document(
        annotation: str | None = "Краткая аннотация.",
        contents: str | None = "1. Общие сведения 1",
        duplicate_annotation: bool = False,
        limitations: str = "Функциональные ограничения отсутствуют.",
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
        add_paragraph("Содержание", "Heading 1")

        if contents:
            add_paragraph(contents, "toc 1")

    sections = [
        (
            "Общие сведения",
            [
                "Программа ТЕСТ.00001-01 «Тестовая программа». "
                "Необходима ОС. Язык программирования — Python.",
            ],
        ),
        (
            "Функциональное назначение",
            [
                "Программа предназначена для обработки данных.",
                limitations,
            ],
        ),
        (
            "Описание логической структуры",
            [
                "Программа состоит из связанных модулей приёма "
                "и обработки данных.",
            ],
        ),
        (
            "Используемые технические средства",
            ["Используются персональная ЭВМ и сетевой адаптер."],
        ),
        (
            "Вызов и загрузка",
            ["Программа вызывается с носителя через исполняемый модуль."],
        ),
        (
            "Входные данные",
            ["Входные данные описаны вместе с форматом и кодированием."],
        ),
        (
            "Выходные данные",
            ["Выходные данные описаны вместе с форматом и кодированием."],
        ),
    ]

    for heading, content_lines in sections:
        add_paragraph(heading, "Heading 1")

        for text in content_lines:
            if text:
                add_paragraph(text)

    return {"blocks": blocks}


def make_opr_ai_result(status: str = "pass") -> dict:
    return {
        "checks": [
            {
                "rule_id": f"OPR-{number:02d}",
                "observation": "Тестовое наблюдение.",
                "status": status,
                "comment": "Тестовый комментарий ИИ.",
                "evidence": [],
            }
            for number in range(1, 10)
        ]
    }


class OprTests(unittest.TestCase):

    def test_opr_information_parts_and_section_matching(self):
        document = make_opr_document()
        opr_structure = extract_opr_structure(document)
        rule_facts = build_opr_rule_facts(opr_structure)

        information_parts = rule_facts["information_parts"]
        candidates = rule_facts["section_candidates"]

        self.assertEqual(
            information_parts["OPR-01"]["recognition_status"],
            "ok",
        )
        self.assertEqual(
            information_parts["OPR-02"]["recognition_status"],
            "ok",
        )
        self.assertTrue(
            information_parts["OPR-01"]["has_content"]
        )
        self.assertTrue(
            information_parts["OPR-02"]["has_content"]
        )

        for number in range(3, 10):
            rule_id = f"OPR-{number:02d}"

            with self.subTest(rule_id=rule_id):
                self.assertEqual(
                    candidates[rule_id]["match_status"],
                    "found",
                )
                self.assertNotIn("status", candidates[rule_id])

        control = run_opr_control(document)
        statuses = {
            check["rule_id"]: check["status"]
            for check in control["checks"]
        }

        self.assertEqual(statuses["OPR-01"], "pass")
        self.assertEqual(statuses["OPR-02"], "pass")
        self.assertEqual(statuses["OPR-04"], "review")

    def test_opr_control_special_cases(self):
        cases = (
            (
                "missing_parts",
                make_opr_document(
                    annotation=None,
                    contents=None,
                    limitations="",
                ),
                {
                    "OPR-01": "fail",
                    "OPR-02": "fail",
                    "OPR-04": "fail",
                },
            ),
            (
                "empty_parts",
                make_opr_document(
                    annotation="",
                    contents="",
                ),
                {
                    "OPR-01": "fail",
                    "OPR-02": "fail",
                    "OPR-04": "review",
                },
            ),
            (
                "ambiguous_annotation",
                make_opr_document(
                    duplicate_annotation=True,
                ),
                {
                    "OPR-01": "review",
                    "OPR-02": "pass",
                    "OPR-04": "review",
                },
            ),
        )

        for case_name, document, expected in cases:
            with self.subTest(case_name=case_name):
                control = run_opr_control(document)
                statuses = {
                    check["rule_id"]: check["status"]
                    for check in control["checks"]
                }

                self.assertEqual(statuses, expected)

    def test_opr_control_disagreement_becomes_review(self):
        document = make_opr_document(limitations="")
        ai_result = make_opr_ai_result(status="pass")
        original_ai_result = copy.deepcopy(ai_result)

        final_result = combine_results(
            ai_result,
            document,
            OPR_NORMATIVE_PROFILE,
        )

        checks = {
            check["rule_id"]: check
            for check in final_result["checks"]
        }

        # Python нашёл аннотацию, а ИИ ошибочно дал pass в этом тесте
        # только OPR-01 не расходится: оба контура возвращают pass.
        self.assertEqual(checks["OPR-01"]["status"], "pass")
        self.assertTrue(checks["OPR-01"]["agreement"])

        # ИИ дал pass, а Python не нашёл сведений об ограничениях.
        self.assertEqual(checks["OPR-04"]["status"], "review")
        self.assertFalse(checks["OPR-04"]["agreement"])
        self.assertEqual(checks["OPR-04"]["ai"]["status"], "pass")
        self.assertEqual(
            checks["OPR-04"]["control"]["status"],
            "fail",
        )

        # Содержательное правило OPR-03 пока не контролируется Python.
        self.assertIsNone(checks["OPR-03"]["control"])
        self.assertIsNone(checks["OPR-03"]["agreement"])
        self.assertEqual(checks["OPR-03"]["status"], "pass")

        self.assertEqual(ai_result, original_ai_result)
        self.assertEqual(
            final_result["document_type"],
            "Описание программы",
        )

    def test_opr_check_uses_nine_isolated_ai_requests(self):
        document = make_opr_document()

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

            if rule_id in {"OPR-01", "OPR-02"}:
                self.assertIn(
                    "information_parts",
                    user_content["document"],
                )
                self.assertNotIn(
                    "main_sections",
                    user_content["document"],
                )
            else:
                self.assertIn(
                    "main_sections",
                    user_content["document"],
                )
                self.assertEqual(
                    len(user_content["document"]["main_sections"]),
                    7,
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
                    profile_id="opr",
                )

        self.assertEqual(mocked_request.call_count, 9)
        self.assertEqual(usage["request_count"], 9)
        self.assertEqual(usage["prompt_tokens"], 90)
        self.assertEqual(usage["completion_tokens"], 45)
        self.assertEqual(usage["total_tokens"], 135)

        self.assertEqual(
            [
                check["rule_id"]
                for check in result["checks"]
            ],
            [
                f"OPR-{number:02d}"
                for number in range(1, 10)
            ],
        )


if __name__ == "__main__":
    unittest.main()