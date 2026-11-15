import shutil
import subprocess
import tempfile
from pathlib import Path


PDF_CONVERSION_TIMEOUT = 120


def convert_docx_to_pdf(
    source_path: str | Path,
    output_path: str | Path,
) -> Path:
    source = Path(source_path)
    output = Path(output_path)

    executable = shutil.which("libreoffice") or shutil.which("soffice")

    if executable is None:
        raise RuntimeError(
            "LibreOffice не найден. Установи LibreOffice Writer "
            "или добавь soffice в PATH."
        )

    if not source.is_file():
        raise ValueError(f"DOCX-файл не найден: {source}")

    if output.suffix.lower() != ".pdf":
        raise ValueError("Выходной файл должен иметь расширение .pdf")

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory(
        prefix="espd_pdf_",
        dir=output.parent,
    ) as temporary_directory:
        temporary_path = Path(temporary_directory)
        profile_path = temporary_path / "libreoffice-profile"

        command = [
            executable,
            f"-env:UserInstallation={profile_path.as_uri()}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temporary_path),
            str(source.resolve()),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=PDF_CONVERSION_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                "Превышено время ожидания конвертации DOCX в PDF"
            ) from error

        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout).strip()

            raise RuntimeError(
                f"LibreOffice не смог преобразовать DOCX в PDF. {details}"
            )

        converted_path = temporary_path / f"{source.stem}.pdf"

        if not converted_path.is_file():
            details = (completed.stdout or completed.stderr).strip()

            raise RuntimeError(f"LibreOffice завершился без создания PDF. {details}")

        converted_path.replace(output)

    return output
