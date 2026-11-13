from backend.profiles.ved.fact_extractor import (
    REQUIRED_HEADERS,
    clean_text,
    extract_document_facts,
    get_row_cells,
)


def iter_text_items(document_structure: dict):
    """
    Возвращает все абзацы и ячейки таблиц с их evidence ID.
    Порядок следования соответствует порядку элементов в DOCX.
    """
    for block in document_structure.get("blocks", []):
        block_type = block.get("type")

        if block_type == "paragraph":
            yield {
                "evidence_id": block["id"],
                "text": clean_text(block.get("text", "")),
            }

        elif block_type == "table":
            for row in block.get("rows", []):
                for cell in get_row_cells(row):
                    yield {
                        "evidence_id": cell["id"],
                        "text": clean_text(cell.get("text", "")),
                    }


def make_check(
        rule_id: str,
        status: str,
        comment: str,
        evidence: list[str] | None = None,
) -> dict:
    return {
        "rule_id": rule_id,
        "status": status,
        "comment": comment,
        "evidence": evidence or [],
        "checker": "python",
    }


def check_required_section(document_structure: dict) -> dict:
    """
    VED-01.
    Ищет точное название раздела среди абзацев и ячеек всех таблиц.
    """
    heading_evidence = [
        item["evidence_id"]
        for item in iter_text_items(document_structure)
        if item["text"].casefold() == "документы на программу"
    ]

    if heading_evidence:
        return make_check(
            rule_id="VED-01",
            status="pass",
            comment="Раздел «Документы на программу» найден.",
            evidence=heading_evidence,
        )

    return make_check(
        rule_id="VED-01",
        status="fail",
        comment="Раздел «Документы на программу» не найден.",
    )


def check_required_headers(facts: dict) -> tuple[dict, list[str]]:
    """
    VED-03.
    Проверяет наличие обязательных граф в выбранной основной таблице.
    Возвращает результат проверки и список отсутствующих граф.
    """
    selection_status = facts.get("table_selection", "not_found")
    headers = facts.get("first_table_headers", [])
    evidence = [header["evidence_id"] for header in headers]

    if selection_status == "ambiguous":
        check = make_check(
            rule_id="VED-03",
            status="review",
            comment=(
                "Найдено несколько одинаково подходящих таблиц. "
                "Основная таблица ведомости не выбрана автоматически."
            ),
        )
        return check, []

    actual_headers = {
        clean_text(header.get("text", "")).casefold()
        for header in headers
    }

    missing_headers = [
        required_header
        for required_header in REQUIRED_HEADERS
        if required_header.casefold() not in actual_headers
    ]

    if missing_headers:
        check = make_check(
            rule_id="VED-03",
            status="fail",
            comment=(
                    "Отсутствующие графы: "
                    + ", ".join(missing_headers)
            ),
            evidence=evidence,
        )
        return check, missing_headers

    check = make_check(
        rule_id="VED-03",
        status="pass",
        comment="Все обязательные графы присутствуют.",
        evidence=evidence,
    )
    return check, []


def check_header_order(
        facts: dict,
        missing_headers: list[str],
) -> dict:
    """
    VED-04.
    Проверяет порядок граф только при наличии всех обязательных граф.
    """
    selection_status = facts.get("table_selection", "not_found")
    headers = facts.get("first_table_headers", [])
    evidence = [header["evidence_id"] for header in headers]

    if selection_status == "ambiguous":
        return make_check(
            rule_id="VED-04",
            status="review",
            comment=(
                "Порядок граф не проверен: "
                "основная таблица ведомости не выбрана однозначно."
            ),
        )

    if missing_headers:
        return make_check(
            rule_id="VED-04",
            status="review",
            comment=(
                "Полный порядок нельзя проверить: "
                "отсутствуют обязательные графы."
            ),
            evidence=evidence,
        )

    actual_order = [
        clean_text(header.get("text", "")).casefold()
        for header in headers
    ]
    expected_order = [
        header.casefold()
        for header in REQUIRED_HEADERS
    ]

    if actual_order == expected_order:
        return make_check(
            rule_id="VED-04",
            status="pass",
            comment="Порядок обязательных граф соответствует требованиям.",
            evidence=evidence,
        )

    actual_titles = [
        clean_text(header.get("text", ""))
        for header in headers
    ]

    return make_check(
        rule_id="VED-04",
        status="fail",
        comment=(
                "Порядок граф не соответствует требованиям. "
                "Ожидаемый порядок: "
                + ", ".join(REQUIRED_HEADERS)
                + ". Фактический порядок: "
                + ", ".join(actual_titles)
                + "."
        ),
        evidence=evidence,
    )


def check_document_kind_codes(facts: dict) -> dict:
    """
    VED-06.
    Проверяет строгое возрастание кодов только среди обозначений,
    извлечённых из документных строк основной таблицы.
    """
    selection_status = facts.get("table_selection", "not_found")
    designations = facts.get("document_designations", [])
    evidence = [
        designation["evidence_id"]
        for designation in designations
    ]

    if selection_status == "ambiguous":
        return make_check(
            rule_id="VED-06",
            status="review",
            comment=(
                "Порядок кодов не проверен: "
                "основная таблица ведомости не выбрана однозначно."
            ),
        )

    if not designations:
        return make_check(
            rule_id="VED-06",
            status="review",
            comment=(
                "Не удалось извлечь обозначения документов "
                "из основной таблицы."
            ),
        )

    raw_codes = [
        designation.get("document_kind_code")
        for designation in designations
    ]

    if any(code is None for code in raw_codes):
        return make_check(
            rule_id="VED-06",
            status="review",
            comment="Не все коды видов документов удалось извлечь.",
            evidence=evidence,
        )

    codes = [int(code) for code in raw_codes]

    strictly_increasing = all(
        current_code > previous_code
        for previous_code, current_code in zip(codes, codes[1:])
    )

    if strictly_increasing:
        return make_check(
            rule_id="VED-06",
            status="pass",
            comment=f"Коды расположены по возрастанию: {codes}",
            evidence=evidence,
        )

    return make_check(
        rule_id="VED-06",
        status="fail",
        comment=(
            "Коды видов документов не расположены "
            f"строго по возрастанию: {codes}"
        ),
        evidence=evidence,
    )


def check_program_section_records(facts: dict) -> dict:
    """
    VED-05.
    Контролирует объективный признак самовключения ведомости:
    наличие записи с кодом вида 20 в разделе программы.

    Полную семантическую оценку остальных записей выполняет ИИ.
    """
    selection_status = facts.get("table_selection", "not_found")

    if selection_status != "ok":
        return make_check(
            rule_id="VED-05",
            status="review",
            comment=(
                "Самовключение ведомости не проверено: "
                "основная таблица не выбрана однозначно."
            ),
        )

    program_entries = [
        designation
        for designation in facts.get("document_designations", [])
        if designation.get("section") == "program"
    ]

    if not program_entries:
        return make_check(
            rule_id="VED-05",
            status="review",
            comment=(
                "В разделе «Документы на программу» "
                "не удалось выделить документные записи."
            ),
        )

    code_20_entries = [
        entry
        for entry in program_entries
        if entry.get("document_kind_code") == "20"
    ]

    if code_20_entries:
        return make_check(
            rule_id="VED-05",
            status="fail",
            comment=(
                "В разделе «Документы на программу» обнаружена "
                "запись с кодом вида 20. Раздел не должен включать "
                "саму Ведомость эксплуатационных документов."
            ),
            evidence=[
                entry["evidence_id"]
                for entry in code_20_entries
            ],
        )

    return make_check(
        rule_id="VED-05",
        status="pass",
        comment=(
            "Записи с кодом вида 20 в разделе "
            "«Документы на программу» не обнаружены."
        ),
        evidence=[
            entry["evidence_id"]
            for entry in program_entries
        ],
    )

def run_structural_control(document_structure: dict) -> dict:
    """
    Независимый программный контроль выбранных структурных правил.
    ИИ не вызывается.
    """
    facts = extract_document_facts(document_structure)

    ved_01 = check_required_section(document_structure)
    ved_03, missing_headers = check_required_headers(facts)
    ved_04 = check_header_order(facts, missing_headers)
    ved_05 = check_program_section_records(facts)
    ved_06 = check_document_kind_codes(facts)

    return {
        "checks": [
            ved_01,
            ved_03,
            ved_04,
            ved_05,
            ved_06,
        ]
    }