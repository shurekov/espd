import json
import sys
from pathlib import Path

from backend.docx_reader import read_docx

ALLOWED_STATUSES = {"pass", "fail", "review"}


def get_expected_rule_ids(normative_profile: dict) -> list[str]:
    rules = normative_profile.get("rules")

    if not isinstance(rules, list) or not rules:
        raise ValueError(
            "В нормативном профиле должен быть непустой массив rules"
        )

    rule_ids = [rule.get("id") for rule in rules]

    if any(
            not isinstance(rule_id, str) or not rule_id.strip()
            for rule_id in rule_ids
    ):
        raise ValueError(
            "Каждое правило профиля должно иметь непустой строковый id"
        )

    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError(
            "В нормативном профиле обнаружены повторяющиеся id правил"
        )

    return rule_ids


def collect_evidence_ids(document_structure: dict) -> set[str]:
    evidence_ids = set()

    for block in document_structure["blocks"]:
        evidence_ids.add(block["id"])

        if block["type"] == "table":
            for row in block["rows"]:
                for cell in row:
                    evidence_ids.add(cell["id"])

    return evidence_ids


def validate_result(
        result: dict,
        document_structure: dict,
        normative_profile: dict,
) -> dict:
    """Проверяет техническую корректность ответа, не меняя вердикты ИИ."""
    errors = []
    checks = result.get("checks")

    if not isinstance(checks, list):
        raise ValueError("Поле checks должно быть массивом")

    expected_rule_ids = get_expected_rule_ids(normative_profile)
    expected_rule_id_set = set(expected_rule_ids)

    rule_ids = [check.get("rule_id") for check in checks]

    if len(checks) != len(expected_rule_ids):
        errors.append(
            f"Ожидалось проверок: {len(expected_rule_ids)}, "
            f"получено: {len(checks)}"
        )

    if set(rule_ids) != expected_rule_id_set:
        errors.append(
            f"Неверный набор правил. "
            f"Ожидалось: {expected_rule_ids}, получено: {rule_ids}"
        )

    if len(set(rule_ids)) != len(rule_ids):
        errors.append(
            "Некоторые правила встречаются более одного раза"
        )

    valid_evidence_ids = collect_evidence_ids(document_structure)

    for check in checks:
        rule_id = check.get("rule_id", "неизвестное правило")

        if check.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{rule_id}: недопустимый статус")

        if not str(check.get("observation", "")).strip():
            errors.append(f"{rule_id}: пустое observation")

        if not str(check.get("comment", "")).strip():
            errors.append(f"{rule_id}: пустой comment")

        evidence = check.get("evidence", [])

        if not isinstance(evidence, list):
            errors.append(f"{rule_id}: evidence должно быть массивом")
            continue

        unknown_ids = set(evidence) - valid_evidence_ids

        if unknown_ids:
            errors.append(
                f"{rule_id}: несуществующие доказательства: "
                f"{sorted(unknown_ids)}"
            )

    if errors:
        raise ValueError("\n".join(errors))

    return result


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Использование: python result_validator.py "
            "<результат.json> <документ.docx> <профиль.json>"
        )
        sys.exit(1)

    result = json.loads(
        Path(sys.argv[1]).read_text(encoding="utf-8")
    )
    document_structure = read_docx(sys.argv[2])
    normative_profile = json.loads(
        Path(sys.argv[3]).read_text(encoding="utf-8")
    )

    try:
        validate_result(
            result,
            document_structure,
            normative_profile,
        )
    except ValueError as error:
        print("Результат модели отклонён:")
        print(error)
        sys.exit(1)

    print("Структура результата и доказательства прошли проверку.")