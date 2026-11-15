from backend.profiles.common_diagnostics import build_sectioned_diagnostics
from backend.profiles.common_payload import (
    build_sectioned_ai_document,
    build_sectioned_rule_facts,
)

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


def build_rop_rule_facts(rop_structure: dict) -> dict:
    return build_sectioned_rule_facts(
        rop_structure,
        (
            ("ROP-01", "annotation"),
            ("ROP-02", "contents"),
        ),
        SECTION_ALIASES,
    )


def build_rop_ai_document(rop_structure: dict) -> dict:
    return build_sectioned_ai_document(rop_structure)


def build_rop_rule_input(
    rule_id: str,
    ai_document: dict,
    rule_facts: dict,
) -> tuple[dict, dict]:
    if rule_id in {"ROP-01", "ROP-02"}:
        part_name = "annotation" if rule_id == "ROP-01" else "contents"

        single_document = {
            "information_parts": {
                part_name: ai_document["information_parts"][part_name],
            },
        }
        single_rule_facts = {
            "information_parts": {
                rule_id: rule_facts["information_parts"][rule_id],
            },
        }

        return single_document, single_rule_facts

    candidate = rule_facts["section_candidates"][rule_id]
    all_sections = ai_document["main_sections"]

    if candidate["match_status"] == "found":
        heading_ids = set(candidate["heading_evidence"])
        selected_sections = [
            section
            for section in all_sections
            if section["heading_evidence"] in heading_ids
        ]
    else:
        # Если точный раздел не найден или найден неоднозначно,
        # ищем требуемое содержание среди всех основных разделов.
        selected_sections = all_sections

    if not selected_sections:
        selected_sections = all_sections

    single_document = {
        "main_sections": selected_sections,
    }
    single_rule_facts = {
        "section_candidates": {
            rule_id: candidate,
        },
        "note": rule_facts["note"],
    }

    return single_document, single_rule_facts


def build_rop_payload(
    _document_structure: dict,
    rop_structure: dict,
) -> tuple[dict, dict]:
    return (
        build_rop_ai_document(rop_structure),
        build_rop_rule_facts(rop_structure),
    )


def build_rop_diagnostics(
    _document_structure: dict,
    rop_structure: dict,
) -> dict:
    return build_sectioned_diagnostics(
        "ROP",
        rop_structure,
        build_rop_rule_facts(rop_structure),
    )
