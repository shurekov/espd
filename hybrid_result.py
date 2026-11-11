import json
import sys
from collections import Counter
from pathlib import Path

from control_checker import run_structural_control
from docx_reader import read_docx

CONTROLLED_RULES = {"VED-01", "VED-03", "VED-04", "VED-06"}


def build_summary(checks: list[dict]) -> str:
    counts = Counter(check["status"] for check in checks)

    return (
        "Выполнено шесть выбранных проверок по ГОСТ 19.507-79: "
        f"pass — {counts['pass']}, fail — {counts['fail']}, "
        f"review — {counts['review']}. "
        "ИИ участвовал во всех шести проверках. Структурные правила "
        "дополнительно проверены независимым программным контуром. "
        "Результат не является заключением о полном соответствии документа "
        "ГОСТ 19.507-79 или ЕСПД."
    )


def combine_results(ai_result: dict, document_structure: dict) -> dict:
    control_result = run_structural_control(document_structure)
    control_by_rule = {
        check["rule_id"]: check
        for check in control_result["checks"]
    }
    combined_checks = []

    for ai_check in ai_result["checks"]:
        rule_id = ai_check["rule_id"]
        control_check = control_by_rule.get(rule_id)
        combined = {
            "rule_id": rule_id,
            "observation": ai_check["observation"],
            "evidence": ai_check["evidence"],
            "ai": {
                "status": ai_check["status"],
                "comment": ai_check["comment"],
            },
            "control": None,
            "agreement": None,
        }

        if rule_id in CONTROLLED_RULES and control_check:
            ai_status = ai_check["status"]
            control_status = control_check["status"]
            agreement = ai_status == control_status

            combined["control"] = {
                "status": control_status,
                "comment": control_check["comment"],
                "evidence": control_check["evidence"],
            }
            combined["agreement"] = agreement

            if agreement:
                combined["status"] = ai_status
                combined["comment"] = ai_check["comment"]
            else:
                combined["status"] = "review"
                combined["comment"] = (
                    "Результаты контуров различаются. "
                    f"ИИ: {ai_status} — {ai_check['comment']} "
                    f"Контроль: {control_status} — {control_check['comment']} "
                    "Требуется ручная проверка."
                )
        else:
            combined["status"] = ai_check["status"]
            combined["comment"] = ai_check["comment"]

        combined_checks.append(combined)

    return {
        "document_type": ai_result["document_type"],
        "standard": ai_result["standard"],
        "checks": combined_checks,
        "summary": build_summary(combined_checks),
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Использование: python hybrid_result.py "
            "<ответ_ии.json> <документ.docx>"
        )
        sys.exit(1)

    ai_result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    document_structure = read_docx(sys.argv[2])
    result = combine_results(ai_result, document_structure)
    print(json.dumps(result, ensure_ascii=False, indent=2))
