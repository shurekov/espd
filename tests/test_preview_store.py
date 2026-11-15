import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.preview_store import PreviewStore


class PreviewStoreTests(unittest.TestCase):
    def test_creates_and_returns_document(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.docx"
            store = PreviewStore(root=root / "previews")
            check_result = {"checks": []}

            def fake_build(source_path, output_path, result):
                self.assertEqual(Path(source_path), source)
                self.assertEqual(result, check_result)
                Path(output_path).write_bytes(b"%PDF-test")

                return {
                    "evidence_ids": ["P1"],
                    "highlighted_evidence_ids": ["P1"],
                    "unresolved_evidence_ids": [],
                }

            with patch(
                "backend.preview_store.build_document_preview",
                side_effect=fake_build,
            ):
                preview = store.create_preview(source, check_result)

            document_path = store.get_document_path(preview["preview_id"])

            self.assertEqual(document_path.read_bytes(), b"%PDF-test")
            self.assertEqual(
                preview["document_pdf_url"],
                (f"/api/previews/{preview['preview_id']}/document.pdf"),
            )
            self.assertEqual(
                preview["highlighted_evidence_ids"],
                ["P1"],
            )

    def test_expired_preview_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = PreviewStore(
                root=root / "previews",
                ttl_seconds=1,
            )

            def fake_build(source_path, output_path, result):
                Path(output_path).write_bytes(b"%PDF-test")
                return {
                    "evidence_ids": [],
                    "highlighted_evidence_ids": [],
                    "unresolved_evidence_ids": [],
                }

            with (
                patch(
                    "backend.preview_store.build_document_preview",
                    side_effect=fake_build,
                ),
                patch(
                    "backend.preview_store.monotonic",
                    return_value=100,
                ),
            ):
                preview = store.create_preview(
                    root / "source.docx",
                    {"checks": []},
                )

            preview_directory = root / "previews" / preview["preview_id"]
            self.assertTrue(preview_directory.exists())

            with patch(
                "backend.preview_store.monotonic",
                return_value=102,
            ):
                with self.assertRaises(KeyError):
                    store.get_document_path(preview["preview_id"])

            self.assertFalse(preview_directory.exists())


if __name__ == "__main__":
    unittest.main()
