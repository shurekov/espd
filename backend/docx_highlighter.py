from collections.abc import Iterable
from pathlib import Path

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from backend.docx_reader import clean_text, iter_blocks


def shade_cell(cell, fill: str = "FFF2CC") -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))

    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)

    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:fill"), fill)


def highlight_document(
    source_path: str | Path,
    output_path: str | Path,
    evidence_ids: Iterable[str],
) -> set[str]:
    source = Path(source_path)
    output = Path(output_path)

    if source.resolve() == output.resolve():
        raise ValueError("Нельзя изменять исходный DOCX-документ")

    targets = set(evidence_ids)
    document = Document(str(source))

    matched_ids = set()
    paragraph_number = 0
    table_number = 0

    for block in iter_blocks(document):
        if isinstance(block, Paragraph):
            if not clean_text(block.text):
                continue

            paragraph_number += 1
            evidence_id = f"P{paragraph_number}"

            if evidence_id not in targets:
                continue

            for run in block.runs:
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW

            matched_ids.add(evidence_id)

        elif isinstance(block, Table):
            table_number += 1
            table_id = f"T{table_number}"

            if table_id in targets:
                matched_ids.add(table_id)

            for row_number, row in enumerate(block.rows, start=1):
                for column_number, cell in enumerate(row.cells, start=1):
                    cell_id = f"{table_id}.R{row_number}.C{column_number}"

                    if table_id in targets or cell_id in targets:
                        shade_cell(cell)

                    if cell_id in targets:
                        matched_ids.add(cell_id)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    document.save(str(output))

    return matched_ids
