def check_information_part(
    part: dict,
    part_name: str,
) -> dict:
    """Проверяет только наличие и непустоту информационной части."""
    heading_evidence = part.get("heading_evidence")
    content = part.get("content", [])
    status = part.get("status")

    if status == "not_found":
        return {
            "status": "fail",
            "comment": f"Обязательная часть «{part_name}» не найдена.",
            "evidence": [],
        }

    evidence = [heading_evidence] if heading_evidence is not None else []

    if status == "ambiguous":
        return {
            "status": "review",
            "comment": (
                f"Часть «{part_name}» распознана неоднозначно. "
                "Требуется ручная проверка."
            ),
            "evidence": evidence,
        }

    if status != "ok":
        return {
            "status": "review",
            "comment": f"Не удалось определить наличие части «{part_name}».",
            "evidence": evidence,
        }

    if not content:
        return {
            "status": "fail",
            "comment": f"Часть «{part_name}» найдена, но пуста.",
            "evidence": evidence,
        }

    first_content_evidence = content[0].get("evidence_id")

    if first_content_evidence:
        evidence.append(first_content_evidence)

    return {
        "status": "pass",
        "comment": f"Часть «{part_name}» найдена и не пуста.",
        "evidence": evidence,
    }
