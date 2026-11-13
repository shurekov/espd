import json
import sys
from pathlib import Path

from backend.docx_reader import read_docx
from backend.profiles.rsp.rsp_structure import (
    extract_rsp_structure,
    normalize_text,
)


def check_information_part(
        part: dict,
        part_name: str,
) -> dict:
    heading_evidence = part.get("heading_evidence")
    content = part.get("content", [])
    status = part.get("status")

    if status == "not_found":
        return {
            "status": "fail",
            "comment": f"Обязательная часть «{part_name}» не найдена.",
            "evidence": [],
        }

    evidence = (
        [heading_evidence]
        if heading_evidence is not None
        else []
    )

    if status == "ambiguous":
        return {
            "status": "review",
            "comment": (
                f"Часть «{part_name}» распознана неоднозначно. "
                "Требуется ручная проверка."
            ),
            "evidence": evidence,
        }

    if status != "ok":
        return {
            "status": "review",
            "comment": (
                f"Не удалось определить наличие части «{part_name}»."
            ),
            "evidence": evidence,
        }

    if not content:
        return {
            "status": "fail",
            "comment": f"Часть «{part_name}» найдена, но пуста.",
            "evidence": evidence,
        }

    first_content_evidence = content[0].get("evidence_id")

    if first_content_evidence:
        evidence.append(first_content_evidence)

    return {
        "status": "pass",
        "comment": f"Часть «{part_name}» найдена и не пуста.",
        "evidence": evidence,
    }

def check_messages(rsp_structure: dict) -> dict:
    sections = [
        section
        for section in rsp_structure.get("main_sections", [])
        if normalize_text(section.get("heading", ""))
           == "сообщения системному программисту"
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
            "evidence": [
                section["heading_evidence"]
                for section in sections
            ],
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
            "не выдаёт сообщений",
            "не выдает сообщений",
            "сообщения отсутствуют",
            "сообщений нет",
            "сообщения не предусмотрены",
        )

        if any(marker in text for marker in absence_markers):
            return {
                "status": "pass",
                "comment": "Документ прямо указывает на отсутствие сообщений.",
                "evidence": evidence,
            }

    # Таблицу нельзя оценивать только по её наличию:
    # нужны смысловая проверка заголовков, сообщений и действий.
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
                    "но не их конкретные тексты и действия."
                ),
                "evidence": evidence,
            }

    return {
        "status": "review",
        "comment": (
            "Структура перечня сообщений неоднозначна. "
            "Требуется ручная проверка."
        ),
        "evidence": evidence,
    }

def run_rsp_control(document_structure: dict) -> dict:
    rsp_structure = extract_rsp_structure(document_structure)
    messages_check = check_messages(rsp_structure)

    annotation_check = check_information_part(
        rsp_structure["annotation"],
        "Аннотация",
    )
    contents_check = check_information_part(
        rsp_structure["contents"],
        "Содержание",
    )

    return {
        "checks": [
            {
                "rule_id": "RSP-01",
                **annotation_check,
            },
            {
                "rule_id": "RSP-02",
                **contents_check,
            },
            {
                "rule_id": "RSP-08",
                **messages_check,
            },
        ]
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Использование: python rsp_control.py "
            "<руководство.docx>"
        )
        sys.exit(1)

    document_structure = read_docx(Path(sys.argv[1]))
    result = run_rsp_control(document_structure)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )