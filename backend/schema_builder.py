from backend.result_validator import get_expected_rule_ids


def build_result_schema(normative_profile: dict) -> dict:
    rule_ids = get_expected_rule_ids(normative_profile)
    rule_count = len(rule_ids)

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "checks": {
                "type": "array",
                "minItems": rule_count,
                "maxItems": rule_count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "rule_id": {
                            "type": "string",
                            "enum": rule_ids,
                        },
                        "observation": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 400,
                        },
                        "status": {
                            "type": "string",
                            "enum": [
                                "pass",
                                "fail",
                                "review",
                            ],
                        },
                        "comment": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 250,
                        },
                        "evidence": {
                            "type": "array",
                            "items": {
                                "type": "string",
                            },
                            "uniqueItems": True,
                        },
                    },
                    "required": [
                        "rule_id",
                        "observation",
                        "status",
                        "comment",
                        "evidence",
                    ],
                },
            },
        },
        "required": [
            "checks",
        ],
    }