import json
import sys
from pathlib import Path

from backend.profiles.opr.opr_structure import normalize_text


SECTION_ALIASES = {
    "OPR-03": {
        "общие сведения",
        "общие сведения о программе",
    },
    "OPR-04": {
        "функциональное назначение",
        "назначение программы",
        "назначение и функции программы",
    },
    "OPR-05": {
        "описание логической структуры",
        "логическая структура",
        "описание структуры программы",
    },
    "OPR-06": {
        "используемые технические средства",
        "технические средства",
    },
    "OPR-07": {
        "вызов и загрузка",
        "вызов программы",
        "загрузка программы",
    },
    "OPR-08": {
        "входные данные",
    },
    "OPR-09": {
        "выходные данные",
    },
}


def match_rule_sections(opr_structure: dict) -> dict:
    """Сопоставляет правила с разделами по нормализованным заголовкам."""
    main_sections = opr_structure.get("main_sections", [])
    result = {}

    for rule_id, aliases in SECTION_ALIASES.items():
        matches = [
            section
            for section in main_sections
            if normalize_text(section.get("heading", "")) in aliases
        ]

        if not matches:
            match_status = "not_found"
        elif len(matches) == 1:
            match_status = "found"
        else:
            match_status = "ambiguous"

        result[rule_id] = {
            "match_status": match_status,
            "headings": [
                section.get("heading", "")
                for section in matches
            ],
            "heading_evidence": [
                section.get("heading_evidence")
                for section in matches
            ],
        }

    return result


def build_opr_rule_facts(opr_structure: dict) -> dict:
    """Формирует структурные факты без оценки соответствия."""
    information_parts = {}

    for rule_id, part_name in (
            ("OPR-01", "annotation"),
            ("OPR-02", "contents"),
    ):
        part = opr_structure.get(part_name, {})
        content = part.get("content", [])

        information_parts[rule_id] = {
            "recognition_status": part.get("status"),
            "heading_evidence": part.get("heading_evidence"),
            "has_content": bool(content),
            "content_evidence": [
                block.get("evidence_id")
                for block in content
            ],
        }

    return {
        "information_parts": information_parts,
        "section_candidates": match_rule_sections(opr_structure),
        "note": (
            "Сопоставление разделов является только структурным фактом. "
            "not_found не означает нарушение: содержание может находиться "
            "в объединённом или переименованном разделе."
        ),
    }


def build_opr_ai_document(opr_structure: dict) -> dict:
    """Формирует документ для последующих отдельных запросов к ИИ."""
    return {
        "information_parts": {
            "annotation": opr_structure.get("annotation", {}),
            "contents": opr_structure.get("contents", {}),
        },
        "main_sections": opr_structure.get("main_sections", []),
    }


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


if __name__ == "__main__":
    main()