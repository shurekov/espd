import re


REQUIRED_HEADERS = [
    "Обозначение",
    "Наименование",
    "Кол. экз.",
    "Местонахождение",
]


# Варианты написания используются только для поиска основной таблицы.
# Они автоматически не признаются соответствующими обязательной форме.
HEADER_ALIASES = {
    "Обозначение": {
        "обозначение",
    },
    "Наименование": {
        "наименование",
    },
    "Кол. экз.": {
        "кол. экз.",
        "кол-во экз.",
        "количество экз.",
        "количество экземпляров",
    },
    "Местонахождение": {
        "местонахождение",
    },
}


SECTION_TITLES = {
    "документы на программу": "program",
    "документы на составные части программы": "components",
    "перечень папок": "folders",
}


CODE_PATTERN = re.compile(
    r"(?<!\d)\d{2}\s+(\d{2})\s+\d{2}(?!\d)"
)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_header(text: str) -> str:
    return clean_text(text).casefold()


def get_canonical_header(text: str) -> str | None:
    normalized = normalize_header(text)

    for canonical_header, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return canonical_header

    return None


def get_row_cells(row: dict | list) -> list:
    if isinstance(row, dict):
        return row.get("cells", [])

    return row


def find_statement_table(
        document_structure: dict,
) -> tuple[dict | None, int | None, str]:
    """
    Ищет основную таблицу ведомости по её заголовкам.

    Возвращает:
    - таблицу;
    - индекс строки заголовков;
    - статус выбора: ok, not_found или ambiguous.
    """
    candidates = []

    for block in document_structure.get("blocks", []):
        if block.get("type") != "table":
            continue

        best_table_candidate = None

        for row_index, row in enumerate(block.get("rows", [])):
            cells = get_row_cells(row)

            canonical_headers = {
                canonical
                for cell in cells
                if (
                       canonical := get_canonical_header(
                           cell.get("text", "")
                       )
                   )
                   is not None
            }

            # Без этих двух граф нельзя уверенно идентифицировать
            # таблицу как основную таблицу ведомости.
            if not {"Обозначение", "Наименование"}.issubset(
                    canonical_headers
            ):
                continue

            candidate = {
                "table": block,
                "header_row_index": row_index,
                "score": len(canonical_headers),
            }

            if (
                    best_table_candidate is None
                    or candidate["score"] > best_table_candidate["score"]
            ):
                best_table_candidate = candidate

        if best_table_candidate is not None:
            candidates.append(best_table_candidate)

    if not candidates:
        return None, None, "not_found"

    best_score = max(
        candidate["score"]
        for candidate in candidates
    )

    best_candidates = [
        candidate
        for candidate in candidates
        if candidate["score"] == best_score
    ]

    # Нельзя автоматически выбирать одну из нескольких
    # одинаково подходящих таблиц.
    if len(best_candidates) > 1:
        return None, None, "ambiguous"

    selected = best_candidates[0]

    return (
        selected["table"],
        selected["header_row_index"],
        "ok",
    )

def find_section_before_table(
        document_structure: dict,
        statement_table_id: str | None,
) -> str | None:
    """
    Находит последний известный заголовок раздела,
    расположенный перед основной таблицей.
    """
    current_section = None

    for block in document_structure.get("blocks", []):
        if (
                block.get("type") == "table"
                and block.get("id") == statement_table_id
        ):
            break

        texts = []

        if block.get("type") == "paragraph":
            texts.append(block.get("text", ""))

        elif block.get("type") == "table":
            for row in block.get("rows", []):
                for cell in get_row_cells(row):
                    texts.append(cell.get("text", ""))

        for text in texts:
            normalized_text = clean_text(text).casefold()
            section = SECTION_TITLES.get(normalized_text)

            if section is not None:
                current_section = section

    return current_section

def extract_document_facts(document_structure: dict) -> dict:
    table, header_row_index, selection_status = find_statement_table(
        document_structure
    )

    result = {
        # Старое имя поля сохранено для совместимости
        # с текущим control_checker.py.
        "first_table_headers": [],
        "document_designations": [],
        "statement_table_id": None,
        "table_selection": selection_status,
    }

    if table is None or header_row_index is None:
        return result

    rows = table.get("rows", [])
    header_cells = get_row_cells(rows[header_row_index])

    result["statement_table_id"] = table.get("id")

    result["first_table_headers"] = [
        {
            "evidence_id": cell["id"],
            "text": clean_text(cell.get("text", "")),
        }
        for cell in header_cells
        if clean_text(cell.get("text", ""))
    ]

    designation_column_index = next(
        (
            index
            for index, cell in enumerate(header_cells)
            if get_canonical_header(cell.get("text", ""))
               == "Обозначение"
        ),
        None,
    )

    name_column_index = next(
        (
            index
            for index, cell in enumerate(header_cells)
            if get_canonical_header(cell.get("text", ""))
               == "Наименование"
        ),
        None,
    )

    if designation_column_index is None or name_column_index is None:
        return result

    current_section = find_section_before_table(
        document_structure,
        table.get("id"),
    )

    # Обрабатываем только строки ниже заголовков основной таблицы.
    for row in rows[header_row_index + 1:]:
        cells = get_row_cells(row)

        section_title = ""

        if name_column_index < len(cells):
            section_title = clean_text(
                cells[name_column_index].get("text", "")
            ).casefold()

        if section_title in SECTION_TITLES:
            current_section = SECTION_TITLES[section_title]
            continue

        if designation_column_index >= len(cells):
            continue

        designation_cell = cells[designation_column_index]
        designation = clean_text(
            designation_cell.get("text", "")
        )

        if not designation:
            continue

        code_match = CODE_PATTERN.search(designation)

        # Строка без обозначения ЕСПД может быть продолжением
        # наименования или служебной строкой. Она не создаёт
        # отдельную запись документа.
        if code_match is None:
            continue

        result["document_designations"].append(
            {
                "evidence_id": designation_cell["id"],
                "designation": designation,
                "document_kind_code": code_match.group(1),
                "section": current_section,
            }
        )

    return result