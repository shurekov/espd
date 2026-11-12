from control_checker import (
    iter_text_items,
    run_structural_control,
)
from fact_extractor import (
    REQUIRED_HEADERS,
    SECTION_TITLES,
    extract_document_facts,
)


CONTROLLED_RULES = {
    "VED-01",
    "VED-03",
    "VED-04",
    "VED-05",
    "VED-06",
}


def build_diagnostics(document_structure: dict) -> dict:
    """
    Временная техническая диагностика.

    Данные извлекаются программно и не требуют дополнительного
    обращения к модели.
    """
    facts = extract_document_facts(document_structure)

    blocks = document_structure.get("blocks", [])
    tables = [
        block
        for block in blocks
        if block.get("type") == "table"
    ]
    paragraphs = [
        block
        for block in blocks
        if block.get("type") == "paragraph"
    ]

    headers = facts.get("first_table_headers", [])
    actual_headers = [
        header.get("text", "")
        for header in headers
    ]

    actual_headers_normalized = {
        header.casefold()
        for header in actual_headers
    }

    missing_headers = [
        required_header
        for required_header in REQUIRED_HEADERS
        if required_header.casefold()
           not in actual_headers_normalized
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
            "statement_table_id": facts.get(
                "statement_table_id"
            ),
        },
        "headers": {
            "expected": REQUIRED_HEADERS,
            "actual": actual_headers,
            "missing_exact": missing_headers,
            "evidence": [
                header.get("evidence_id")
                for header in headers
            ],
        },
        "section_headings": section_headings,
        "document_designations": designations,
        "sections": {
            "program": {
                "entries": program_entries,
                "document_kind_codes": [
                    entry.get("document_kind_code")
                    for entry in program_entries
                ],
                "has_code_20_entries": any(
                    entry.get("document_kind_code") == "20"
                    for entry in program_entries
                ),
            },
            "components": {
                "entries": component_entries,
                "document_kind_codes": [
                    entry.get("document_kind_code")
                    for entry in component_entries
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


def build_summary(checks: list[dict]) -> str:
    status_counts = {
        "pass": 0,
        "fail": 0,
        "review": 0,
    }

    for check in checks:
        status = check["status"]

        if status in status_counts:
            status_counts[status] += 1

    return (
        "Выполнено шесть выбранных проверок по ГОСТ 19.507-79: "
        f"pass — {status_counts['pass']}, "
        f"fail — {status_counts['fail']}, "
        f"review — {status_counts['review']}. "
        "ИИ участвовал во всех шести проверках. "
        "Структурные правила дополнительно проверены "
        "независимым программным контуром. "
        "Результат не является заключением о полном соответствии "
        "документа ГОСТ 19.507-79 или ЕСПД."
    )


def combine_results(
        ai_result: dict,
        document_structure: dict,
) -> dict:
    control_result = run_structural_control(document_structure)

    control_by_id = {
        check["rule_id"]: check
        for check in control_result["checks"]
    }

    combined_checks = []

    for ai_check in ai_result["checks"]:
        rule_id = ai_check["rule_id"]
        ai_status = ai_check["status"]
        ai_comment = ai_check["comment"]
        final_evidence = ai_check.get("evidence", [])

        control_check = control_by_id.get(rule_id)
        public_control = None
        agreement = None

        if (
                rule_id in CONTROLLED_RULES
                and control_check is not None
        ):
            control_status = control_check["status"]
            agreement = ai_status == control_status

            public_control = {
                "status": control_status,
                "comment": control_check["comment"],
                "evidence": control_check.get("evidence", []),
            }

            if agreement:
                final_status = control_status
                final_comment = control_check["comment"]
                final_evidence = control_check.get("evidence", [])

            else:
                final_status = "review"
                final_comment = (
                    "Результаты контуров различаются. "
                    f"ИИ: {ai_status} — {ai_comment} "
                    f"Контроль: {control_status} — "
                    f"{control_check['comment']} "
                    "Требуется ручная проверка."
                )
        else:
            final_status = ai_status
            final_comment = ai_comment

        combined_checks.append(
            {
                "rule_id": rule_id,
                "observation": ai_check["observation"],
                "evidence": final_evidence,
                "ai": {
                    "status": ai_status,
                    "comment": ai_comment,
                    "evidence": ai_check.get("evidence", []),
                },
                "control": public_control,
                "agreement": agreement,
                "status": final_status,
                "comment": final_comment,
            }
        )

    return {
        "document_type": ai_result.get("document_type", ""),
        "standard": ai_result.get("standard", ""),
        "checks": combined_checks,
        "summary": build_summary(combined_checks),
        "diagnostics": build_diagnostics(document_structure),
    }