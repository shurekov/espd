from backend.profiles.common_structure import match_sections_by_aliases


def build_information_part_facts(
    profile_structure: dict,
    rule_parts: tuple[tuple[str, str], ...],
) -> dict:
    information_parts = {}

    for rule_id, part_name in rule_parts:
        part = profile_structure.get(part_name, {})
        content = part.get("content", [])

        information_parts[rule_id] = {
            "recognition_status": part.get("status"),
            "heading_evidence": part.get("heading_evidence"),
            "has_content": bool(content),
            "content_evidence": [block.get("evidence_id") for block in content],
        }

    return information_parts


def build_sectioned_ai_document(profile_structure: dict) -> dict:
    return {
        "information_parts": {
            "annotation": profile_structure.get("annotation", {}),
            "contents": profile_structure.get("contents", {}),
        },
        "main_sections": profile_structure.get("main_sections", []),
    }


def build_sectioned_rule_facts(
    profile_structure: dict,
    rule_parts: tuple[tuple[str, str], ...],
    section_aliases: dict[str, set[str]],
) -> dict:
    return {
        "information_parts": build_information_part_facts(
            profile_structure,
            rule_parts,
        ),
        "section_candidates": match_sections_by_aliases(
            profile_structure,
            section_aliases,
        ),
        "note": (
            "Сопоставление разделов является только структурным фактом. "
            "not_found не означает нарушение: содержание может находиться "
            "в объединённом или переименованном разделе."
        ),
    }
