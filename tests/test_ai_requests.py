import json
import unittest
from unittest.mock import Mock

from backend.ai_requests import request_isolated_ai_results


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


def build_rule_input(
    rule_id: str,
    ai_document: dict,
    rule_facts: dict,
) -> tuple[dict, dict]:
    return (
        {"rule_id": rule_id},
        {"rule_id": rule_id},
    )


def make_check(rule_id: str, status: str = "review") -> dict:
    return {
        "rule_id": rule_id,
        "observation": "Тестовое наблюдение.",
        "status": status,
        "comment": "Тестовый комментарий.",
        "evidence": [],
    }


class AiRequestsTests(unittest.TestCase):
    def test_accumulates_usage_from_all_requests(self):
        payloads = []

        def fake_request(payload):
            payloads.append(payload)

            user_content = json.loads(
                payload["messages"][1]["content"],
            )
            rule_id = user_content["rule"]["id"]

            return {
                "checks": [make_check(rule_id)],
            }, {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }

        result, usage = request_isolated_ai_results(
            document_structure=DOCUMENT_STRUCTURE,
            ai_document={},
            rule_facts={},
            normative_profile=NORMATIVE_PROFILE,
            model="test-model",
            request_ai_result=fake_request,
            build_system_prompt=lambda rule_id: f"Prompt {rule_id}",
            build_rule_input=build_rule_input,
            max_tokens=123,
        )

        self.assertEqual(
            [check["rule_id"] for check in result["checks"]],
            ["TEST-01", "TEST-02"],
        )
        self.assertEqual(
            usage,
            {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
                "request_count": 2,
            },
        )
        self.assertEqual(len(payloads), 2)
        self.assertEqual(
            [payload["max_tokens"] for payload in payloads],
            [123, 123],
        )

    def test_invalid_rule_result_stops_following_requests(self):
        request = Mock(
            return_value=(
                {
                    "checks": [
                        make_check(
                            "TEST-01",
                            status="invalid",
                        )
                    ],
                },
                {},
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "недопустимый статус",
        ):
            request_isolated_ai_results(
                document_structure=DOCUMENT_STRUCTURE,
                ai_document={},
                rule_facts={},
                normative_profile=NORMATIVE_PROFILE,
                model="test-model",
                request_ai_result=request,
                build_system_prompt=lambda rule_id: f"Prompt {rule_id}",
                build_rule_input=build_rule_input,
            )

        self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
