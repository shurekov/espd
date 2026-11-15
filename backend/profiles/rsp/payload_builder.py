from backend.profiles.common_diagnostics import build_sectioned_diagnostics
from backend.profiles.common_payload import (
    build_sectioned_ai_document,
    build_sectioned_rule_facts,
)

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


def build_rsp_rule_facts(rsp_structure: dict) -> dict:
    return build_sectioned_rule_facts(
        rsp_structure,
        (
            ("RSP-01", "annotation"),
            ("RSP-02", "contents"),
        ),
        SECTION_ALIASES,
    )


def build_rsp_ai_document(rsp_structure: dict) -> dict:
    return build_sectioned_ai_document(rsp_structure)


def build_rsp_rule_input(
    rule_id: str,
    ai_document: dict,
    rule_facts: dict,
) -> tuple[dict, dict]:
    if rule_id in {"RSP-01", "RSP-02"}:
        part_name = "annotation" if rule_id == "RSP-01" else "contents"

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

    if candidate["match_status"] == "found" and rule_id != "RSP-04":
        heading_ids = set(candidate["heading_evidence"])
        selected_sections = [
            section
            for section in all_sections
            if section["heading_evidence"] in heading_ids
        ]
    else:
        # Если точный раздел не найден или найден неоднозначно,
        # нужно искать содержание среди всех разделов.
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


def build_rsp_payload(
    _document_structure: dict,
    rsp_structure: dict,
) -> tuple[dict, dict]:
    return (
        build_rsp_ai_document(rsp_structure),
        build_rsp_rule_facts(rsp_structure),
    )


def build_rsp_diagnostics(
    _document_structure: dict,
    rsp_structure: dict,
) -> dict:
    return build_sectioned_diagnostics(
        "RSP",
        rsp_structure,
        build_rsp_rule_facts(rsp_structure),
    )
