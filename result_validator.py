import json
import sys
from pathlib import Path

from docx_reader import read_docx

EXPECTED_RULE_IDS = {f"VED-{number:02d}" for number in range(1, 7)}
ALLOWED_STATUSES = {"pass", "fail", "review"}


def collect_evidence_ids(document_structure: dict) -> set[str]:
    evidence_ids = set()

    for block in document_structure["blocks"]:
        evidence_ids.add(block["id"])
        if block["type"] == "table":
            for row in block["rows"]:
                for cell in row:
                    evidence_ids.add(cell["id"])

    return evidence_ids


def validate_result(result: dict, document_structure: dict) -> dict:
    """Проверяет техническую корректность ответа, не меняя вердикты ИИ."""
    errors = []
    checks = result.get("checks")

    if not isinstance(checks, list):
        raise ValueError("Поле checks должно быть массивом")

    rule_ids = [check.get("rule_id") for check in checks]

    if len(checks) != 6:
        errors.append(f"Ожидалось 6 проверок, получено: {len(checks)}")
    if set(rule_ids) != EXPECTED_RULE_IDS:
        errors.append(f"Неверный набор правил: {rule_ids}")
    if len(set(rule_ids)) != len(rule_ids):
        errors.append("Некоторые правила встречаются более одного раза")

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
                f"{rule_id}: несуществующие доказательства: {sorted(unknown_ids)}"
            )

    if errors:
        raise ValueError("\n".join(errors))

    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Использование: python result_validator.py "
            "<результат.json> <документ.docx>"
        )
        sys.exit(1)

    result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    document_structure = read_docx(sys.argv[2])

    try:
        validate_result(result, document_structure)
    except ValueError as error:
        print("Результат модели отклонён:")
        print(error)
        sys.exit(1)

    print("Структура результата и доказательства прошли проверку.")
