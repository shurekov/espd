from backend.profiles.ved.control_checker import iter_text_items
from backend.profiles.ved.fact_extractor import (
    REQUIRED_HEADERS,
    SECTION_TITLES,
    extract_document_facts,
)


def build_diagnostics(
    document_structure: dict,
    facts: dict | None = None,
) -> dict:
    """
    Временная техническая диагностика.

    Данные извлекаются программно и не требуют дополнительного
    обращения к модели.
    """
    if facts is None:
        facts = extract_document_facts(document_structure)

    blocks = document_structure.get("blocks", [])
    tables = [block for block in blocks if block.get("type") == "table"]
    paragraphs = [block for block in blocks if block.get("type") == "paragraph"]

    headers = facts.get("first_table_headers", [])
    actual_headers = [header.get("text", "") for header in headers]

    actual_headers_normalized = {header.casefold() for header in actual_headers}

    missing_headers = [
        required_header
        for required_header in REQUIRED_HEADERS
        if required_header.casefold() not in actual_headers_normalized
    ]

    designations = facts.get("document_designations", [])

    program_entries = [
        designation
        for designation in designations
        if designation.get("section") == "program"
    ]

    component_entries = [
        designation
        for designation in designations
        if designation.get("section") == "components"
    ]

    folder_entries = [
        designation
        for designation in designations
        if designation.get("section") == "folders"
    ]

    entries_without_section = [
        designation
        for designation in designations
        if designation.get("section") is None
    ]

    section_headings = {
        "program": [],
        "components": [],
        "folders": [],
    }

    for item in iter_text_items(document_structure):
        normalized_text = item["text"].casefold()
        section = SECTION_TITLES.get(normalized_text)

        if section is not None:
            section_headings[section].append(
                {
                    "evidence_id": item["evidence_id"],
                    "text": item["text"],
                }
            )

    return {
        "note": (
            "Временная техническая диагностика. "
            "Не является дополнительным заключением о соответствии."
        ),
        "document_overview": {
            "paragraph_count": len(paragraphs),
            "table_count": len(tables),
            "tables": [
                {
                    "table_id": table.get("id"),
                    "row_count": len(table.get("rows", [])),
                }
                for table in tables
            ],
        },
        "table_selection": {
            "status": facts.get("table_selection"),
            "statement_table_id": facts.get("statement_table_id"),
        },
        "headers": {
            "expected": REQUIRED_HEADERS,
            "actual": actual_headers,
            "missing_exact": missing_headers,
            "evidence": [header.get("evidence_id") for header in headers],
        },
        "section_headings": section_headings,
        "document_designations": designations,
        "sections": {
            "program": {
                "entries": program_entries,
                "document_kind_codes": [
                    entry.get("document_kind_code") for entry in program_entries
                ],
                "has_code_20_entries": any(
                    entry.get("document_kind_code") == "20" for entry in program_entries
                ),
            },
            "components": {
                "entries": component_entries,
                "document_kind_codes": [
                    entry.get("document_kind_code") for entry in component_entries
                ],
            },
            "folders": {
                "entries": folder_entries,
            },
            "without_section": {
                "entries": entries_without_section,
            },
        },
    }
