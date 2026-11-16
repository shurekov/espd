import json
import sys
from pathlib import Path

from backend.profiles.common_control import check_information_part
from backend.docx_reader import read_docx
from backend.profiles.common_structure import normalize_text
from backend.profiles.opr.opr_structure import extract_opr_structure


def check_functional_limitations(opr_structure: dict) -> dict:
    """
    Выполняет ограниченный контроль сведений об ограничениях (OPR-5).

    Python не оценивает смысл найденных ограничений. Он только
    обнаруживает явные упоминания либо их отсутствие.
    """
    main_sections = opr_structure.get("main_sections", [])
    mention_evidence = []

    for section in main_sections:
        for block in section.get("content", []):
            text = normalize_text(block.get("text", ""))

            if "огранич" in text:
                mention_evidence.append(block["evidence_id"])

    if mention_evidence:
        return {
            "status": "review",
            "comment": (
                "В документе найдены упоминания ограничений. "
                "Их содержание требует смысловой проверки."
            ),
            "evidence": mention_evidence[:4],
        }

    purpose_aliases = {
        "функциональное назначение",
        "назначение программы",
        "назначение и функции программы",
    }
    purpose_sections = [
        section
        for section in main_sections
        if normalize_text(section.get("heading", "")) in purpose_aliases
    ]

    evidence = []

    if purpose_sections:
        section = purpose_sections[0]
        evidence.append(section["heading_evidence"])

        content = section.get("content", [])

        if content:
            evidence.append(content[0]["evidence_id"])

    return {
        "status": "fail",
        "comment": (
            "В основных разделах не найдено явных сведений "
            "о функциональных ограничениях на применение программы."
        ),
        "evidence": evidence,
    }


def run_opr_control(
    document_structure: dict,
    opr_structure: dict | None = None,
) -> dict:
    """Выполняет независимый контроль ограниченного набора правил OPR."""
    if opr_structure is None:
        opr_structure = extract_opr_structure(document_structure)

    annotation_check = check_information_part(
        opr_structure["annotation"],
        "Аннотация",
    )
    contents_check = check_information_part(
        opr_structure["contents"],
        "Содержание",
    )
    limitations_check = check_functional_limitations(opr_structure)

    return {
        "checks": [
            {
                "rule_id": "OPR-2.1",
                **annotation_check,
            },
            {
                "rule_id": "OPR-2.2",
                **contents_check,
            },
            {
                "rule_id": "OPR-5",
                **limitations_check,
            },
        ]
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Использование: python -m backend.profiles.opr.opr_control <описание.docx>"
        )

    document_structure = read_docx(Path(sys.argv[1]))
    result = run_opr_control(document_structure)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
