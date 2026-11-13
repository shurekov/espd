from backend.profiles.rsp.rsp_structure import normalize_text

SECTION_ALIASES = {
    "RSP-03": {
        "общие сведения о программе",
        "общие сведения",
    },
    "RSP-04": {
        "структура программы",
        "структура",
    },
    "RSP-05": {
        "настройка программы",
        "настройка",
    },
    "RSP-06": {
        "проверка программы",
        "проверка",
    },
    "RSP-07": {
        "дополнительные возможности",
    },
    "RSP-08": {
        "сообщения системному программисту",
    },
}


def match_rule_sections(rsp_structure: dict) -> dict:
    main_sections = rsp_structure.get("main_sections", [])
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


def build_rsp_rule_facts(rsp_structure: dict) -> dict:
    information_parts = {}

    for rule_id, part_name in (
            ("RSP-01", "annotation"),
            ("RSP-02", "contents"),
    ):
        part = rsp_structure.get(part_name, {})
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
        "section_candidates": match_rule_sections(rsp_structure),
        "note": (
            "Сопоставление разделов является только структурным фактом. "
            "not_found не означает нарушение: содержание может находиться "
            "в объединённом или переименованном разделе."
        ),
    }


def build_rsp_ai_document(rsp_structure: dict) -> dict:
    return {
        "information_parts": {
            "annotation": rsp_structure.get("annotation", {}),
            "contents": rsp_structure.get("contents", {}),
        },
        "main_sections": rsp_structure.get("main_sections", []),
    }