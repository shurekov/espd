from collections.abc import Callable


def normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def is_change_registration_table(block: dict) -> bool:
    if block.get("type") != "table":
        return False

    rows = block.get("rows", [])

    if not rows:
        return False

    first_row_text = " ".join(cell.get("text", "") for cell in rows[0])

    return "лист регистрации изменений" in normalize_text(first_row_text)


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
        rows_text.append(" | ".join(cell.get("text", "") for cell in row))

    return {
        "evidence_id": block["id"],
        "type": "table",
        "text": "\n".join(rows_text),
    }


def extract_sectioned_structure(
    document_structure: dict,
    info_headings: dict[str, str],
    is_main_heading: Callable[[dict], bool],
) -> dict:
    blocks = document_structure.get("blocks", [])

    info_candidates = {part: [] for part in info_headings.values()}

    for index, block in enumerate(blocks):
        if block.get("type") != "paragraph":
            continue

        part = info_headings.get(normalize_text(block.get("text", "")))

        if part is not None:
            info_candidates[part].append(index)

    main_heading_indices = [
        index for index, block in enumerate(blocks) if is_main_heading(block)
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

                if text in info_headings:
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

        main_sections.append(
            {
                "heading": heading.get("text", ""),
                "heading_evidence": heading["id"],
                "style": heading.get("style", ""),
                "content": content,
            }
        )

    information_parts = {part: build_info_part(part) for part in info_candidates}

    registration_tables = [
        block["id"] for block in blocks if is_change_registration_table(block)
    ]

    return {
        **information_parts,
        "main_sections": main_sections,
        "registration_change_tables": registration_tables,
    }


def match_sections_by_aliases(
    profile_structure: dict,
    section_aliases: dict[str, set[str]],
) -> dict:
    main_sections = profile_structure.get("main_sections", [])
    result = {}

    for rule_id, aliases in section_aliases.items():
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
            "headings": [section.get("heading", "") for section in matches],
            "heading_evidence": [
                section.get("heading_evidence") for section in matches
            ],
        }

    return result


def is_main_heading_block(
    block: dict,
    info_headings: dict[str, str],
    known_main_headings: set[str],
    subordinate_heading_styles: set[str] | None = None,
) -> bool:
    if block.get("type") != "paragraph":
        return False

    text = normalize_text(block.get("text", ""))

    if text in info_headings:
        return False

    style = normalize_text(block.get("style", ""))
    compact_style = style.replace(" ", "")

    if (
        subordinate_heading_styles is not None
        and compact_style in subordinate_heading_styles
    ):
        return False

    if compact_style in {"heading1", "заголовок1"}:
        return True

    return text in known_main_headings
