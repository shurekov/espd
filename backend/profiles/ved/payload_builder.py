from backend.profiles.ved.fact_extractor import (
    REQUIRED_HEADERS,
    clean_text,
    get_row_cells,
)


def compact_table(table: dict) -> dict:
    """
    Удаляет полностью пустые строки таблицы.
    Evidence ID и позиции ячеек сохраняются.
    """
    compact_rows = []

    for row in table.get("rows", []):
        cells = get_row_cells(row)

        has_text = any(
            clean_text(cell.get("text", ""))
            for cell in cells
        )

        if not has_text:
            continue

        if isinstance(row, dict):
            compact_row = {
                **row,
                "cells": cells,
            }
        else:
            compact_row = cells

        compact_rows.append(compact_row)

    return {
        **table,
        "rows": compact_rows,
    }


def build_ai_document(
        document_structure: dict,
        document_facts: dict,
) -> dict:
    """
    Сохраняет все абзацы и основную таблицу ведомости.
    """
    selection_status = document_facts.get(
        "table_selection",
        "not_found",
    )
    statement_table_id = document_facts.get(
        "statement_table_id"
    )

    if selection_status != "ok" or not statement_table_id:
        return document_structure

    ai_blocks = []

    for block in document_structure.get("blocks", []):
        block_type = block.get("type")

        if block_type == "paragraph":
            ai_blocks.append(block)

        elif (
                block_type == "table"
                and block.get("id") == statement_table_id
        ):
            ai_blocks.append(compact_table(block))

    return {
        "blocks": ai_blocks,
    }


def build_rule_facts(document_facts: dict) -> dict:
    """
    Формирует явные программные факты для отдельных правил.
    Не содержит готовых статусов проверок.
    """
    headers = document_facts.get("first_table_headers", [])

    actual_headers = [
        clean_text(header.get("text", ""))
        for header in headers
    ]

    actual_headers_normalized = {
        header.casefold()
        for header in actual_headers
    }

    missing_exact_headers = [
        required_header
        for required_header in REQUIRED_HEADERS
        if required_header.casefold()
           not in actual_headers_normalized
    ]

    designations = document_facts.get(
        "document_designations",
        [],
    )

    program_entries = [
        entry
        for entry in designations
        if entry.get("section") == "program"
    ]

    return {
        "table_selection": {
            "status": document_facts.get("table_selection"),
            "statement_table_id": document_facts.get(
                "statement_table_id"
            ),
        },
        "VED-03": {
            "required_exact_headers": REQUIRED_HEADERS,
            "actual_headers": actual_headers,
            "missing_exact_headers": missing_exact_headers,
        },
        "VED-04": {
            "required_header_order": REQUIRED_HEADERS,
            "actual_header_order": actual_headers,
            "full_order_can_be_checked": (
                    not missing_exact_headers
                    and document_facts.get("table_selection") == "ok"
            ),
        },
        "VED-05": {
            "program_entries": program_entries,
            "program_document_kind_codes": [
                entry.get("document_kind_code")
                for entry in program_entries
            ],
            "has_code_20_entries": any(
                entry.get("document_kind_code") == "20"
                for entry in program_entries
            ),
        },
        "VED-06": {
            "entries_in_document_order": designations,
            "document_kind_codes_in_order": [
                entry.get("document_kind_code")
                for entry in designations
            ],
        },
    }