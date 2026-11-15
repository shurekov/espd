import copy
import unittest

from backend.result_validator import validate_result


DOCUMENT_STRUCTURE = {
    "blocks": [
        {
            "id": "P1",
            "type": "paragraph",
            "style": "Normal",
            "text": "Тестовый документ",
        }
    ]
}

NORMATIVE_PROFILE = {
    "rules": [
        {"id": "TEST-01"},
        {"id": "TEST-02"},
    ]
}


def make_result(rule_ids=("TEST-01", "TEST-02")) -> dict:
    return {
        "checks": [
            {
                "rule_id": rule_id,
                "observation": "Тестовое наблюдение.",
                "status": "review",
                "comment": "Тестовый комментарий.",
                "evidence": ["P1"],
            }
            for rule_id in rule_ids
        ]
    }


class ResultValidatorTests(unittest.TestCase):
    def test_invalid_status_and_empty_required_fields_are_rejected(self):
        cases = (
            ("status", "unknown", "недопустимый статус"),
            ("observation", "   ", "пустое observation"),
            ("comment", "", "пустой comment"),
        )

        for field, value, expected_error in cases:
            with self.subTest(field=field):
                result = make_result()
                result["checks"][0][field] = value

                with self.assertRaisesRegex(
                    ValueError,
                    expected_error,
                ):
                    validate_result(
                        result,
                        DOCUMENT_STRUCTURE,
                        NORMATIVE_PROFILE,
                    )

    def test_duplicate_and_missing_rules_are_rejected(self):
        cases = (
            (
                make_result(("TEST-01", "TEST-01")),
                "более одного раза",
            ),
            (
                make_result(("TEST-02",)),
                "Неверный набор правил",
            ),
        )

        for result, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                original_result = copy.deepcopy(result)

                with self.assertRaisesRegex(
                    ValueError,
                    expected_error,
                ):
                    validate_result(
                        result,
                        DOCUMENT_STRUCTURE,
                        NORMATIVE_PROFILE,
                    )

                self.assertEqual(result, original_result)


if __name__ == "__main__":
    unittest.main()
