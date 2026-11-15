import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.pdf_converter import convert_docx_to_pdf


class PdfConverterTests(unittest.TestCase):
    @patch("backend.pdf_converter.subprocess.run")
    @patch("backend.pdf_converter.shutil.which")
    def test_successful_conversion(
        self,
        mocked_which,
        mocked_run,
    ):
        mocked_which.return_value = "/usr/bin/libreoffice"

        def fake_run(command, **kwargs):
            output_directory = Path(command[command.index("--outdir") + 1])
            (output_directory / "source.pdf").write_bytes(
                b"%PDF-test",
            )

            return SimpleNamespace(
                returncode=0,
                stdout="",
                stderr="",
            )

        mocked_run.side_effect = fake_run

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.docx"
            output = Path(temporary_directory) / "result.pdf"
            source.write_bytes(b"test-docx")

            result = convert_docx_to_pdf(source, output)

            self.assertEqual(result, output)
            self.assertEqual(output.read_bytes(), b"%PDF-test")

            command = mocked_run.call_args.args[0]
            self.assertIn("--headless", command)
            self.assertIn("--convert-to", command)

    @patch("backend.pdf_converter.shutil.which")
    def test_missing_libreoffice_is_reported(
        self,
        mocked_which,
    ):
        mocked_which.return_value = None

        with self.assertRaisesRegex(
            RuntimeError,
            "LibreOffice не найден",
        ):
            convert_docx_to_pdf(
                "source.docx",
                "result.pdf",
            )


if __name__ == "__main__":
    unittest.main()
