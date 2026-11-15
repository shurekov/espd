import json
import unittest
from unittest.mock import Mock, patch

from backend.llm_client import request_ai_result


class LlmClientTests(unittest.TestCase):
    @patch("backend.llm_client.requests.post")
    def test_parses_result_and_usage(self, mocked_post):
        expected_result = {
            "checks": [
                {
                    "rule_id": "TEST-01",
                    "status": "pass",
                }
            ]
        }
        expected_usage = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            expected_result,
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
            "usage": expected_usage,
        }
        mocked_post.return_value = response

        result, usage = request_ai_result({"model": "test"})

        self.assertEqual(result, expected_result)
        self.assertEqual(usage, expected_usage)
        mocked_post.assert_called_once()

    @patch("backend.llm_client.requests.post")
    def test_non_success_http_status_is_rejected(self, mocked_post):
        response = Mock()
        response.status_code = 500
        response.text = "Внутренняя ошибка сервера"
        mocked_post.return_value = response

        with self.assertRaisesRegex(
            RuntimeError,
            "HTTP 500",
        ):
            request_ai_result({"model": "test"})

        response.json.assert_not_called()

    @patch("backend.llm_client.requests.post")
    def test_missing_message_content_is_rejected(self, mocked_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [],
        }
        mocked_post.return_value = response

        with self.assertRaisesRegex(
            RuntimeError,
            "не содержит текст результата",
        ):
            request_ai_result({"model": "test"})

    @patch("backend.llm_client.requests.post")
    def test_invalid_result_json_is_rejected(self, mocked_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "{повреждённый json",
                    },
                }
            ],
        }
        mocked_post.return_value = response

        with self.assertRaisesRegex(
            RuntimeError,
            "некорректный JSON результата",
        ):
            request_ai_result({"model": "test"})

    @patch("backend.llm_client.requests.post")
    def test_missing_usage_defaults_to_empty_dict(self, mocked_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"checks": []}),
                    },
                }
            ],
        }
        mocked_post.return_value = response

        result, usage = request_ai_result({"model": "test"})

        self.assertEqual(result, {"checks": []})
        self.assertEqual(usage, {})

    @patch("backend.llm_client.requests.post")
    def test_non_object_response_is_rejected(self, mocked_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = []
        mocked_post.return_value = response

        with self.assertRaisesRegex(
            RuntimeError,
            "не содержит текст результата",
        ):
            request_ai_result({"model": "test"})


if __name__ == "__main__":
    unittest.main()
