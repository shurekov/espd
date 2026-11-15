import json
import sys
from pathlib import Path

from backend.profiles.common_control import check_information_part
from backend.docx_reader import read_docx
from backend.profiles.common_structure import normalize_text
from backend.profiles.rop.rop_structure import extract_rop_structure


def check_messages(rop_structure: dict) -> dict:
    sections = [
        section
        for section in rop_structure.get("main_sections", [])
        if normalize_text(section.get("heading", "")) == "сообщения оператору"
    ]

    if not sections:
        return {
            "status": "review",
            "comment": (
                "Точный раздел сообщений не найден. "
                "Требуется поиск содержания в других разделах."
            ),
            "evidence": [],
        }

    if len(sections) > 1:
        return {
            "status": "review",
            "comment": "Найдено несколько разделов сообщений.",
            "evidence": [section["heading_evidence"] for section in sections],
        }

    section = sections[0]
    content = section.get("content", [])
    evidence = [section["heading_evidence"]]

    if content:
        evidence.append(content[0]["evidence_id"])

    if not content:
        return {
            "status": "fail",
            "comment": "Раздел сообщений найден, но пуст.",
            "evidence": evidence,
        }

    if len(content) == 1:
        text = normalize_text(content[0].get("text", ""))

        absence_markers = (
            "сообщения оператору не выдаются",
            "не выдаёт сообщений оператору",
            "не выдает сообщений оператору",
            "не выдаёт сообщений",
            "не выдает сообщений",
            "сообщения отсутствуют",
            "сообщений нет",
            "сообщения не предусмотрены",
        )

        if any(marker in text for marker in absence_markers):
            return {
                "status": "pass",
                "comment": (
                    "Документ прямо указывает на отсутствие сообщений оператору."
                ),
                "evidence": evidence,
            }

    # Наличие таблицы само по себе не доказывает,
    # что в ней есть тексты сообщений, их содержание и действия оператора.
    if any(block.get("type") == "table" for block in content):
        return {
            "status": "review",
            "comment": (
                "Сообщения представлены таблицей. "
                "Требуется смысловая проверка её содержимого."
            ),
            "evidence": evidence,
        }

    generic_markers = (
        "может выдавать информационные сообщения",
        "могут выдаваться информационные сообщения",
        "оба типа сообщений содержат",
        "сообщения содержат исчерпывающую информацию",
    )

    if len(content) == 1:
        text = normalize_text(content[0].get("text", ""))

        if any(marker in text for marker in generic_markers):
            return {
                "status": "fail",
                "comment": (
                    "Раздел содержит только общее описание сообщений, "
                    "но не их конкретные тексты и действия оператора."
                ),
                "evidence": evidence,
            }

    return {
        "status": "review",
        "comment": (
            "Структура перечня сообщений неоднозначна. Требуется ручная проверка."
        ),
        "evidence": evidence,
    }


def run_rop_control(
    document_structure: dict,
    rop_structure: dict | None = None,
) -> dict:
    if rop_structure is None:
        rop_structure = extract_rop_structure(document_structure)

    annotation_check = check_information_part(
        rop_structure["annotation"],
        "Аннотация",
    )
    contents_check = check_information_part(
        rop_structure["contents"],
        "Содержание",
    )
    messages_check = check_messages(rop_structure)

    return {
        "checks": [
            {
                "rule_id": "ROP-01",
                **annotation_check,
            },
            {
                "rule_id": "ROP-02",
                **contents_check,
            },
            {
                "rule_id": "ROP-06",
                **messages_check,
            },
        ]
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Использование: python -m "
            "backend.profiles.rop.rop_control "
            "<руководство.docx>"
        )
        sys.exit(1)

    document_structure = read_docx(Path(sys.argv[1]))
    result = run_rop_control(document_structure)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
