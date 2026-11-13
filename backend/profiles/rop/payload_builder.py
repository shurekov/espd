from backend.profiles.rop.rop_structure import normalize_text


SECTION_ALIASES = {
    "ROP-03": {
        "назначение программы",
        "общие сведения о программе",
        "общие сведения",
    },
    "ROP-04": {
        "условия выполнения",
        "условия выполнения программы",
    },
    "ROP-05": {
        "выполнение программы",
    },
    "ROP-06": {
        "сообщения оператору",
    },
}


def match_rule_sections(rop_structure: dict) -> dict:
    main_sections = rop_structure.get("main_sections", [])
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


def build_rop_rule_facts(rop_structure: dict) -> dict:
    information_parts = {}

    for rule_id, part_name in (
            ("ROP-01", "annotation"),
            ("ROP-02", "contents"),
    ):
        part = rop_structure.get(part_name, {})
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
        "section_candidates": match_rule_sections(rop_structure),
        "note": (
            "Сопоставление разделов является только структурным фактом. "
            "not_found не означает нарушение: содержание может находиться "
            "в объединённом или переименованном разделе."
        ),
    }


def build_rop_ai_document(rop_structure: dict) -> dict:
    return {
        "information_parts": {
            "annotation": rop_structure.get("annotation", {}),
            "contents": rop_structure.get("contents", {}),
        },
        "main_sections": rop_structure.get("main_sections", []),
    }