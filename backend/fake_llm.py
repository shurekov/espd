import json
from typing import Any


def collect_evidence_ids(value: Any) -> list[str]:
    evidence_ids = []

    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"id", "evidence_id"} and isinstance(item, str):
                evidence_ids.append(item)
            else:
                evidence_ids.extend(collect_evidence_ids(item))

    elif isinstance(value, list):
        for item in value:
            evidence_ids.extend(collect_evidence_ids(item))

    return evidence_ids


def request_fake_ai_result(payload: dict) -> tuple[dict, dict]:
    schema = payload["response_format"]["json_schema"]["schema"]
    rule_ids = schema["properties"]["checks"]["items"]["properties"]["rule_id"]["enum"]

    user_content = json.loads(payload["messages"][1]["content"])
    evidence_ids = collect_evidence_ids(user_content.get("document", {}))
    evidence = evidence_ids[:1]

    statuses = ("fail", "review", "pass")
    checks = []

    for rule_id in rule_ids:
        try:
            rule_number = int(rule_id.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            rule_number = 0

        status = statuses[rule_number % len(statuses)]

        checks.append(
            {
                "rule_id": rule_id,
                "observation": (f"Имитация наблюдения ИИ для правила {rule_id}."),
                "status": status,
                "comment": (
                    "Технический ответ-заглушка. "
                    "Содержание документа моделью не анализировалось."
                ),
                "evidence": evidence,
            }
        )

    return {
        "checks": checks,
    }, {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
