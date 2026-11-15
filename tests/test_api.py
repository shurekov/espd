import io
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

from main import (
    MAX_FILE_SIZE,
    check_uploaded_document,
    get_normative_document,
    get_preview_document,
)


def make_upload(
    filename: str = "document.docx",
    content: bytes = b"test",
) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
    )


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_profile_is_rejected(self):
        upload = make_upload()
        self.addAsyncCleanup(upload.close)

        with self.assertRaises(HTTPException) as context:
            await check_uploaded_document(
                upload,
                profile_id="unknown",
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Неизвестный профиль", context.exception.detail)

    async def test_non_docx_file_is_rejected(self):
        upload = make_upload(filename="document.pdf")
        self.addAsyncCleanup(upload.close)

        with self.assertRaises(HTTPException) as context:
            await check_uploaded_document(
                upload,
                profile_id="ved",
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("только файлы DOCX", context.exception.detail)

    async def test_oversized_file_is_rejected(self):
        upload = make_upload(
            content=b"x" * (MAX_FILE_SIZE + 1),
        )
        self.addAsyncCleanup(upload.close)

        with self.assertRaises(HTTPException) as context:
            await check_uploaded_document(
                upload,
                profile_id="ved",
            )

        self.assertEqual(context.exception.status_code, 413)
        self.assertIn("не должен превышать 10 МБ", context.exception.detail)

    @patch("main.preview_store.create_preview")
    @patch("main.check_document")
    async def test_successful_check_removes_temporary_file(
        self,
        mocked_check,
        mocked_create_preview,
    ):
        checked_path = None

        def fake_check(path, save_outputs, profile_id):
            nonlocal checked_path
            checked_path = Path(path)

            self.assertTrue(checked_path.is_file())
            self.assertFalse(save_outputs)
            self.assertEqual(profile_id, "ved")

            return {
                "checks": [],
            }, {
                "total_tokens": 0,
            }

        def fake_create_preview(path, result):
            self.assertTrue(Path(path).is_file())
            self.assertEqual(result, {"checks": []})

            return {
                "preview_id": "test-preview",
                "document_pdf_url": ("/api/previews/test-preview/document.pdf"),
                "evidence_ids": [],
                "highlighted_evidence_ids": [],
                "unresolved_evidence_ids": [],
            }

        mocked_check.side_effect = fake_check
        mocked_create_preview.side_effect = fake_create_preview
        upload = make_upload()

        response = await check_uploaded_document(
            upload,
            profile_id="ved",
        )

        self.assertEqual(response["filename"], "document.docx")
        self.assertEqual(response["profile_id"], "ved")
        self.assertEqual(response["result"], {"checks": []})
        self.assertEqual(response["usage"], {"total_tokens": 0})
        self.assertEqual(
            response["preview"]["preview_id"],
            "test-preview",
        )
        self.assertEqual(
            response["normative"]["document"]["id"],
            "gost-19.507-79",
        )

        mocked_create_preview.assert_called_once()

        self.assertIsNotNone(checked_path)
        self.assertFalse(checked_path.exists())

    @patch("main.check_document")
    async def test_model_error_becomes_502_and_removes_temporary_file(
        self,
        mocked_check,
    ):
        checked_path = None

        def fake_check(path, save_outputs, profile_id):
            nonlocal checked_path
            checked_path = Path(path)
            raise RuntimeError("Модель недоступна")

        mocked_check.side_effect = fake_check
        upload = make_upload()

        with self.assertRaises(HTTPException) as context:
            await check_uploaded_document(
                upload,
                profile_id="ved",
            )

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("Модель недоступна", context.exception.detail)

        self.assertIsNotNone(checked_path)
        self.assertFalse(checked_path.exists())

    @patch("main.check_document")
    async def test_document_error_becomes_422(
        self,
        mocked_check,
    ):
        mocked_check.side_effect = ValueError(
            "Повреждённый документ",
        )
        upload = make_upload()

        with self.assertRaises(HTTPException) as context:
            await check_uploaded_document(
                upload,
                profile_id="ved",
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("Повреждённый документ", context.exception.detail)

    @patch("main.preview_store.get_document_path")
    async def test_missing_preview_returns_404(
        self,
        mocked_get_document_path,
    ):
        mocked_get_document_path.side_effect = KeyError("missing")

        with self.assertRaises(HTTPException) as context:
            get_preview_document("missing")

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn(
            "PDF-preview не найдено",
            context.exception.detail,
        )

    @patch("main.get_normative_document_path")
    async def test_missing_normative_pdf_returns_404(
        self,
        mocked_get_document_path,
    ):
        mocked_get_document_path.return_value = Path(
            "/missing/normative.pdf"
        )

        with self.assertRaises(HTTPException) as context:
            get_normative_document("gost-19.507-79")

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn(
            "ещё не добавлен",
            context.exception.detail,
        )


if __name__ == "__main__":
    unittest.main()
