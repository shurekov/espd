import json
import sys
from pathlib import Path

from backend.docx_reader import read_docx


INFO_HEADINGS = {
    "аннотация": "annotation",
    "содержание": "contents",
    "оглавление": "contents",
}

KNOWN_MAIN_HEADINGS = {
    "общие сведения о программе",
    "общие сведения",
    "назначение программы",
    "условия выполнения",
    "условия выполнения программы",
    "выполнение программы",
    "сообщения оператору",
    "перечень сокращений",
}

SUBORDINATE_HEADING_STYLES = {
                                 f"heading{level}"
                                 for level in range(2, 10)
                             } | {
                                 f"заголовок{level}"
                                 for level in range(2, 10)
                             }


def normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def is_change_registration_table(block: dict) -> bool:
    if block.get("type") != "table":
        return False

    rows = block.get("rows", [])
    if not rows:
        return False

    first_row_text = " ".join(
        cell.get("text", "")
        for cell in rows[0]
    )

    return (
            "лист регистрации изменений"
            in normalize_text(first_row_text)
    )


def is_main_heading(block: dict) -> bool:
    if block.get("type") != "paragraph":
        return False

    text = normalize_text(block.get("text", ""))

    if text in INFO_HEADINGS:
        return False

    style = normalize_text(block.get("style", ""))
    compact_style = style.replace(" ", "")

    # «Назначение программы» может быть подразделом
    # внутри «Общие сведения о программе».
    if compact_style in SUBORDINATE_HEADING_STYLES:
        return False

    if compact_style in {"heading1", "заголовок1"}:
        return True

    return text in KNOWN_MAIN_HEADINGS


def export_block(block: dict) -> dict:
    if block.get("type") == "paragraph":
        return {
            "evidence_id": block["id"],
            "type": "paragraph",
            "style": block.get("style", ""),
            "text": block.get("text", ""),
        }

    rows_text = []

    for row in block.get("rows", []):
        rows_text.append(
            " | ".join(
                cell.get("text", "")
                for cell in row
            )
        )

    return {
        "evidence_id": block["id"],
        "type": "table",
        "text": "\n".join(rows_text),
    }


def extract_rop_structure(document_structure: dict) -> dict:
    blocks = document_structure.get("blocks", [])

    info_candidates = {
        "annotation": [],
        "contents": [],
    }

    for index, block in enumerate(blocks):
        if block.get("type") != "paragraph":
            continue

        part = INFO_HEADINGS.get(
            normalize_text(block.get("text", ""))
        )

        if part is not None:
            info_candidates[part].append(index)

    main_heading_indices = [
        index
        for index, block in enumerate(blocks)
        if is_main_heading(block)
    ]
    main_heading_index_set = set(main_heading_indices)

    def build_info_part(part: str) -> dict:
        candidates = info_candidates[part]

        if not candidates:
            return {
                "status": "not_found",
                "heading_evidence": None,
                "content": [],
            }

        start = candidates[0]
        status = "ok" if len(candidates) == 1 else "ambiguous"
        content = []

        for index in range(start + 1, len(blocks)):
            block = blocks[index]

            if index in main_heading_index_set:
                break

            if is_change_registration_table(block):
                break

            if block.get("type") == "paragraph":
                text = normalize_text(block.get("text", ""))

                if text in INFO_HEADINGS:
                    break

            content.append(export_block(block))

        return {
            "status": status,
            "heading_evidence": blocks[start]["id"],
            "content": content,
        }

    main_sections = []

    for position, start in enumerate(main_heading_indices):
        heading = blocks[start]

        if position + 1 < len(main_heading_indices):
            end = main_heading_indices[position + 1]
        else:
            end = len(blocks)

        content = []

        for index in range(start + 1, end):
            block = blocks[index]

            if is_change_registration_table(block):
                break

            content.append(export_block(block))

        main_sections.append({
            "heading": heading.get("text", ""),
            "heading_evidence": heading["id"],
            "style": heading.get("style", ""),
            "content": content,
        })

    registration_tables = [
        block["id"]
        for block in blocks
        if is_change_registration_table(block)
    ]

    return {
        "annotation": build_info_part("annotation"),
        "contents": build_info_part("contents"),
        "main_sections": main_sections,
        "registration_change_tables": registration_tables,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Использование: python -m "
            "backend.profiles.rop.rop_structure "
            "<руководство.docx>"
        )
        sys.exit(1)

    document_structure = read_docx(Path(sys.argv[1]))
    result = extract_rop_structure(document_structure)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )