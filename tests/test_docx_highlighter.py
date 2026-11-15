import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn

from backend.docx_highlighter import highlight_document


class DocxHighlighterTests(unittest.TestCase):
    def test_highlights_paragraph_without_changing_source(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.docx"
            output = Path(temporary_directory) / "highlighted.docx"

            document = Document()
            document.add_paragraph("Первый абзац")
            document.add_paragraph("   ")
            document.add_paragraph("Абзац с ошибкой")
            document.save(source)

            matched = highlight_document(
                source,
                output,
                {"P2"},
            )

            self.assertEqual(matched, {"P2"})
            self.assertTrue(output.is_file())

            original = Document(source)
            annotated = Document(output)

            self.assertIsNone(
                original.paragraphs[2].runs[0].font.highlight_color,
            )
            self.assertEqual(
                annotated.paragraphs[2].runs[0].font.highlight_color,
                WD_COLOR_INDEX.YELLOW,
            )
            self.assertIsNone(
                annotated.paragraphs[0].runs[0].font.highlight_color,
            )

    def test_highlights_only_selected_table_cell(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.docx"
            output = Path(temporary_directory) / "highlighted.docx"

            document = Document()
            table = document.add_table(rows=1, cols=2)
            table.cell(0, 0).text = "Первая ячейка"
            table.cell(0, 1).text = "Вторая ячейка"
            document.save(source)

            matched = highlight_document(
                source,
                output,
                {"T1.R1.C2"},
            )

            self.assertEqual(matched, {"T1.R1.C2"})

            annotated = Document(output)
            first_properties = annotated.tables[0].cell(0, 0)._tc.get_or_add_tcPr()
            second_properties = annotated.tables[0].cell(0, 1)._tc.get_or_add_tcPr()

            first_shading = first_properties.find(qn("w:shd"))
            second_shading = second_properties.find(qn("w:shd"))

            self.assertIsNone(first_shading)
            self.assertIsNotNone(second_shading)
            self.assertEqual(
                second_shading.get(qn("w:fill")),
                "FFF2CC",
            )


if __name__ == "__main__":
    unittest.main()
