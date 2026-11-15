from backend.profile_registry import get_profile


def build_summary(
    checks: list[dict],
    normative_profile: dict,
) -> str:
    status_counts = {
        "pass": 0,
        "fail": 0,
        "review": 0,
    }

    for check in checks:
        status = check["status"]

        if status in status_counts:
            status_counts[status] += 1

    standard = normative_profile["standard"]
    check_count = len(checks)
    controlled_count = sum(check.get("control") is not None for check in checks)

    sentences = [
        (f"Выполнено выбранных проверок по {standard}: {check_count}."),
        (
            f"pass — {status_counts['pass']}, "
            f"fail — {status_counts['fail']}, "
            f"review — {status_counts['review']}."
        ),
        "ИИ участвовал в каждой из этих проверок.",
    ]

    if controlled_count:
        sentences.append(
            f"Независимый программный контроль выполнен "
            f"для {controlled_count} из {check_count} правил."
        )

    sentences.append(
        "Результат не является заключением о полном соответствии "
        f"документа {standard} или ЕСПД."
    )

    return " ".join(sentences)


def combine_results(
    ai_result: dict,
    document_structure: dict,
    normative_profile: dict,
    profile_structure: dict | None = None,
) -> dict:
    profile_id = normative_profile.get("profile_id", "ved")
    profile = get_profile(profile_id)

    if profile_structure is None:
        profile_structure = profile.extract_structure(document_structure)

    controlled_rules = profile.controlled_rules
    control_result = profile.run_control(
        document_structure,
        profile_structure,
    )

    diagnostics = profile.build_diagnostics(
        document_structure,
        profile_structure,
    )

    control_by_id = {check["rule_id"]: check for check in control_result["checks"]}

    combined_checks = []

    for ai_check in ai_result["checks"]:
        rule_id = ai_check["rule_id"]
        ai_status = ai_check["status"]
        ai_comment = ai_check["comment"]
        final_evidence = ai_check.get("evidence", [])

        control_check = control_by_id.get(rule_id)
        public_control = None
        agreement = None

        if rule_id in controlled_rules and control_check is not None:
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
        "document_type": normative_profile["document_type"],
        "standard": normative_profile["standard"],
        "checks": combined_checks,
        "summary": build_summary(
            combined_checks,
            normative_profile,
        ),
        "diagnostics": diagnostics,
    }
