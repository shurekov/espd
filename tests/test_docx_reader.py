import tempfile
import unittest
from pathlib import Path

from docx import Document

from backend.docx_reader import read_docx


def read_document(document: Document) -> dict:
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "test.docx"
        document.save(path)
        return read_docx(path)


class DocxReaderTests(unittest.TestCase):
    def test_preserves_block_order_and_evidence_ids(self):
        document = Document()
        document.add_paragraph("  Первый   абзац  ")
        document.add_paragraph("   ")

        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Ячейка 1"
        table.cell(0, 1).text = "Ячейка 2"

        document.add_paragraph("Последний абзац")

        result = read_document(document)
        blocks = result["blocks"]

        self.assertEqual(
            [block["type"] for block in blocks],
            ["paragraph", "table", "paragraph"],
        )
        self.assertEqual(
            [block["id"] for block in blocks],
            ["P1", "T1", "P2"],
        )

        self.assertEqual(blocks[0]["text"], "Первый абзац")
        self.assertEqual(blocks[2]["text"], "Последний абзац")

        cells = blocks[1]["rows"][0]
        self.assertEqual(
            [cell["id"] for cell in cells],
            ["T1.R1.C1", "T1.R1.C2"],
        )
        self.assertEqual(
            [cell["text"] for cell in cells],
            ["Ячейка 1", "Ячейка 2"],
        )

    def test_empty_document_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "не найдено текстовых элементов",
        ):
            read_document(Document())


if __name__ == "__main__":
    unittest.main()
