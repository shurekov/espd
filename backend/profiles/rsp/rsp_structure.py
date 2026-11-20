import json
import sys
from pathlib import Path

from backend.docx_reader import read_docx
from backend.profiles.common_structure import (
    extract_sectioned_structure,
    normalize_text,
    is_main_heading_block,
)

INFO_HEADINGS = {
    "аннотация": "annotation",
    "содержание": "contents",
    "оглавление": "contents",
}

KNOWN_MAIN_HEADINGS = {
    "общие сведения о программе",
    "общие сведения",
    "структура программы",
    "структура",
    "настройка программы",
    "настройка",
    "проверка программы",
    "проверка",
    "дополнительные возможности",
    "сообщения системному программисту",
    "перечень сокращений",
}


def is_main_heading(block: dict) -> bool:
    return is_main_heading_block(
        block,
        INFO_HEADINGS,
        KNOWN_MAIN_HEADINGS,
    )


def is_toc_block(block: dict) -> bool:
    if block.get("type") != "paragraph":
        return False

    style = normalize_text(block.get("style", "")).replace(" ", "")
    return style.startswith("toc") or style.startswith("оглавление")


def is_abbreviations_table(block: dict) -> bool:
    if block.get("type") != "table":
        return False

    text = block.get("text", "")
    first_line = text.splitlines()[0] if text else ""

    return "перечень сокращений" in normalize_text(first_line)


def separate_annotation_from_contents(structure: dict) -> None:
    """
    Отделяет записи содержания от следующего за ними текста.

    Если текст похож на аннотацию без явного заголовка, она получает
    статус ambiguous: программа не должна утверждать, что её нет.
    """
    contents = structure.get("contents", {})
    content = contents.get("content", [])

    toc_indices = [index for index, block in enumerate(content) if is_toc_block(block)]

    if not toc_indices:
        return

    split_at = None

    for index in range(toc_indices[-1] + 1, len(content)):
        if not is_toc_block(content[index]):
            split_at = index
            break

    if split_at is None:
        return

    trailing_content = content[split_at:]
    contents["content"] = content[:split_at]

    annotation = structure.get("annotation", {})

    if annotation.get("status") == "not_found" and trailing_content:
        structure["annotation"] = {
            "status": "ambiguous",
            "heading_evidence": None,
            "content": trailing_content,
        }


def exclude_abbreviations_from_sections(structure: dict) -> None:
    """Не включает таблицу сокращений в предыдущий основной раздел."""
    for section in structure.get("main_sections", []):
        content = section.get("content", [])

        for index, block in enumerate(content):
            if is_abbreviations_table(block):
                section["content"] = content[:index]
                break


def extract_rsp_structure(document_structure: dict) -> dict:
    structure = extract_sectioned_structure(
        document_structure,
        INFO_HEADINGS,
        is_main_heading,
    )

    separate_annotation_from_contents(structure)
    exclude_abbreviations_from_sections(structure)

    return structure


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python rsp_structure.py <руководство.docx>")
        sys.exit(1)

    document_structure = read_docx(Path(sys.argv[1]))
    result = extract_rsp_structure(document_structure)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
