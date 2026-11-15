def build_sectioned_diagnostics(
    profile_name: str,
    profile_structure: dict,
    rule_facts: dict,
) -> dict:
    return {
        "note": (
            f"Структурная диагностика {profile_name}. "
            "Не является дополнительным заключением о соответствии."
        ),
        "structure": profile_structure,
        "rule_facts": rule_facts,
    }
