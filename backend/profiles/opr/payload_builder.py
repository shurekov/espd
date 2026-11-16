import json
import sys
from pathlib import Path

from backend.profiles.common_diagnostics import build_sectioned_diagnostics
from backend.profiles.common_payload import (
    build_sectioned_ai_document,
    build_sectioned_rule_facts,
)

# Ключи соответствуют пунктам ГОСТ 19.402-78:
# OPR-4 — пункт 4 «Общие сведения», OPR-5 — пункт 5 и т. д.
SECTION_ALIASES = {
    "OPR-4": {
        "общие сведения",
        "общие сведения о программе",
    },
    "OPR-5": {
        "функциональное назначение",
        "назначение программы",
        "назначение и функции программы",
    },
    "OPR-6": {
        "описание логической структуры",
        "логическая структура",
        "описание структуры программы",
    },
    "OPR-7": {
        "используемые технические средства",
        "технические средства",
    },
    "OPR-8": {
        "вызов и загрузка",
        "вызов программы",
        "загрузка программы",
    },
    "OPR-9": {
        "входные данные",
    },
    "OPR-10": {
        "выходные данные",
    },
}


def build_opr_rule_facts(opr_structure: dict) -> dict:
    return build_sectioned_rule_facts(
        opr_structure,
        (
            ("OPR-2.1", "annotation"),
            ("OPR-2.2", "contents"),
        ),
        SECTION_ALIASES,
    )


def build_opr_ai_document(opr_structure: dict) -> dict:
    return build_sectioned_ai_document(opr_structure)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Использование: python -m "
            "backend.profiles.opr.payload_builder <opr_structure.json>"
        )

    path = Path(sys.argv[1])
    opr_structure = json.loads(path.read_text(encoding="utf-8"))
    result = build_opr_rule_facts(opr_structure)

    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_opr_rule_input(
    rule_id: str,
    ai_document: dict,
    rule_facts: dict,
) -> tuple[dict, dict]:
    if rule_id in {"OPR-2.1", "OPR-2.2"}:
        part_name = "annotation" if rule_id == "OPR-2.1" else "contents"

        single_document = {
            "information_parts": {
                part_name: ai_document["information_parts"][part_name],
            },
        }
        single_rule_facts = {
            "information_parts": {
                rule_id: rule_facts["information_parts"][rule_id],
            },
        }

        return single_document, single_rule_facts

    candidate = rule_facts["section_candidates"][rule_id]

    # Требуемое содержание может находиться в объединённом
    # или переименованном разделе, поэтому передаём все разделы.
    single_document = {
        "main_sections": ai_document["main_sections"],
    }
    single_rule_facts = {
        "section_candidates": {
            rule_id: candidate,
        },
        "note": rule_facts["note"],
    }

    return single_document, single_rule_facts


def build_opr_payload(
    _document_structure: dict,
    opr_structure: dict,
) -> tuple[dict, dict]:
    return (
        build_opr_ai_document(opr_structure),
        build_opr_rule_facts(opr_structure),
    )


def build_opr_diagnostics(
    _document_structure: dict,
    opr_structure: dict,
) -> dict:
    return build_sectioned_diagnostics(
        "OPR",
        opr_structure,
        build_opr_rule_facts(opr_structure),
    )


if __name__ == "__main__":
    main()
