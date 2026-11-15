import json
from collections.abc import Callable
from time import perf_counter

from backend.result_validator import validate_result
from backend.schema_builder import build_result_schema


def request_isolated_ai_results(
    document_structure: dict,
    ai_document: dict,
    rule_facts: dict,
    normative_profile: dict,
    model: str,
    request_ai_result: Callable[[dict], tuple[dict, dict]],
    build_system_prompt: Callable[[str], str],
    build_rule_input: Callable[[str, dict, dict], tuple[dict, dict]],
    max_tokens: int = 400,
) -> tuple[dict, dict]:
    checks = []
    total_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "request_count": 0,
    }

    for rule in normative_profile["rules"]:
        rule_id = rule["id"]
        single_rule_profile = {
            **normative_profile,
            "rules": [rule],
        }

        single_document, single_rule_facts = build_rule_input(
            rule_id,
            ai_document,
            rule_facts,
        )

        result_schema = build_result_schema(single_rule_profile)

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": build_system_prompt(rule_id),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "rule": rule,
                            "rule_facts": single_rule_facts,
                            "document": single_document,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{rule_id.lower()}_check",
                    "strict": True,
                    "schema": result_schema,
                },
            },
        }

        request_started = perf_counter()
        rule_result, usage = request_ai_result(payload)

        validate_result(
            rule_result,
            document_structure,
            single_rule_profile,
        )

        checks.extend(rule_result["checks"])

        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        ):
            total_usage[key] += usage.get(key, 0)

        total_usage["request_count"] += 1

        print(
            f"[timing] {rule_id}: "
            f"{perf_counter() - request_started:.2f} с; "
            f"токены: {usage.get('total_tokens', 0)}"
        )

    return {"checks": checks}, total_usage
