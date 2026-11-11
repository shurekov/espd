import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def iter_blocks(document):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def read_docx(path: str | Path) -> dict:
    document = Document(str(path))
    blocks = []
    paragraph_number = 0
    table_number = 0

    for block in iter_blocks(document):
        if isinstance(block, Paragraph):
            text = clean_text(block.text)
            if not text:
                continue

            paragraph_number += 1
            blocks.append({
                "id": f"P{paragraph_number}",
                "type": "paragraph",
                "style": block.style.name if block.style else "",
                "text": text,
            })

        elif isinstance(block, Table):
            table_number += 1
            table_id = f"T{table_number}"
            rows = []

            for row_number, row in enumerate(block.rows, start=1):
                cells = []

                for column_number, cell in enumerate(row.cells, start=1):
                    cell_text = clean_text(
                        " ".join(paragraph.text for paragraph in cell.paragraphs)
                    )
                    cells.append({
                        "id": f"{table_id}.R{row_number}.C{column_number}",
                        "text": cell_text,
                    })

                rows.append(cells)

            blocks.append({
                "id": table_id,
                "type": "table",
                "rows": rows,
            })

    if not blocks:
        raise ValueError("В документе не найдено текстовых элементов")

    return {"blocks": blocks}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python docx_reader.py <файл.docx>")
        sys.exit(1)

    result = read_docx(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
