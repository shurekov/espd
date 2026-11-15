import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.document_preview import build_document_preview


class DocumentPreviewTests(unittest.TestCase):
    def test_builds_preview_only_for_fail_and_review(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.docx"
            output = root / "preview.pdf"
            source.write_bytes(b"original")

            check_result = {
                "checks": [
                    {
                        "status": "fail",
                        "evidence": ["P2", "T1.R2.C1"],
                    },
                    {
                        "status": "pass",
                        "evidence": ["P1"],
                    },
                    {
                        "status": "review",
                        "evidence": ["P2", "P3"],
                    },
                ]
            }

            with (
                patch(
                    "backend.document_preview.highlight_document",
                    return_value={"P2", "P3"},
                ) as highlight_mock,
                patch("backend.document_preview.convert_docx_to_pdf") as convert_mock,
            ):
                metadata = build_document_preview(
                    source,
                    output,
                    check_result,
                )

            highlight_mock.assert_called_once()
            highlight_args = highlight_mock.call_args.args

            self.assertEqual(Path(highlight_args[0]), source)
            self.assertEqual(
                highlight_args[2],
                ["P2", "T1.R2.C1", "P3"],
            )

            highlighted_path = Path(highlight_args[1])
            self.assertNotEqual(highlighted_path, source)
            convert_mock.assert_called_once_with(
                highlighted_path,
                output,
            )

            self.assertEqual(
                metadata,
                {
                    "evidence_ids": ["P2", "T1.R2.C1", "P3"],
                    "highlighted_evidence_ids": ["P2", "P3"],
                    "unresolved_evidence_ids": ["T1.R2.C1"],
                },
            )

    def test_builds_preview_without_evidence(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.docx"
            output = root / "preview.pdf"
            source.write_bytes(b"original")

            check_result = {
                "checks": [
                    {
                        "status": "pass",
                        "evidence": ["P1"],
                    }
                ]
            }

            with (
                patch(
                    "backend.document_preview.highlight_document",
                    return_value=set(),
                ) as highlight_mock,
                patch("backend.document_preview.convert_docx_to_pdf") as convert_mock,
            ):
                metadata = build_document_preview(
                    source,
                    output,
                    check_result,
                )

            self.assertEqual(
                highlight_mock.call_args.args[2],
                [],
            )
            convert_mock.assert_called_once()
            self.assertEqual(
                metadata,
                {
                    "evidence_ids": [],
                    "highlighted_evidence_ids": [],
                    "unresolved_evidence_ids": [],
                },
            )


if __name__ == "__main__":
    unittest.main()
