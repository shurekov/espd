import tempfile
from pathlib import Path
from zipfile import BadZipFile

import requests
from docx.opc.exceptions import PackageNotFoundError
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from backend.profile_registry import PROFILES
from backend.check_document import check_document
from backend.preview_store import PreviewStore
from backend.normative_registry import (
    build_profile_normative,
    get_normative_document_path,
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
MAX_FILE_SIZE = 10 * 1024 * 1024

app = FastAPI(title="ЕСПД Контроль")
preview_store = PreviewStore()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "espd-control",
    }


@app.post("/api/check")
async def check_uploaded_document(
    file: UploadFile = File(...),
    profile_id: str = Form("ved"),
) -> dict:
    if profile_id not in PROFILES:
        available_profiles = ", ".join(PROFILES)

        raise HTTPException(
            status_code=400,
            detail=(f"Неизвестный профиль проверки. Допустимо: {available_profiles}"),
        )
    if not file.filename or Path(file.filename).suffix.lower() != ".docx":
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только файлы DOCX",
        )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".docx",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            file_size = 0

            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)

                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Размер DOCX не должен превышать 10 МБ",
                    )

                temporary_file.write(chunk)

        result, usage = await run_in_threadpool(
            check_document,
            temporary_path,
            False,
            profile_id,
        )

        try:
            preview = await run_in_threadpool(
                preview_store.create_preview,
                temporary_path,
                result,
            )
        except RuntimeError as error:
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось создать PDF-preview: {error}",
            ) from error

        normative = build_profile_normative(profile_id)

        return {
            "filename": file.filename,
            "profile_id": profile_id,
            "result": result,
            "usage": usage,
            "preview": preview,
            "normative": normative,
        }

    except HTTPException:
        raise

    except (requests.RequestException, RuntimeError) as error:
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка обращения к модели: {error}",
        ) from error

    except (
        ValueError,
        BadZipFile,
        PackageNotFoundError,
    ) as error:
        raise HTTPException(
            status_code=422,
            detail=f"Не удалось проверить документ: {error}",
        ) from error

    finally:
        await file.close()

        if temporary_path:
            temporary_path.unlink(missing_ok=True)


@app.get("/api/previews/{preview_id}/document.pdf")
def get_preview_document(preview_id: str) -> FileResponse:
    try:
        document_path = preview_store.get_document_path(preview_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="PDF-preview не найдено или срок его хранения истёк",
        ) from None

    return FileResponse(
        document_path,
        media_type="application/pdf",
    )


@app.get("/api/normative-documents/{document_id}.pdf")
def get_normative_document(document_id: str) -> FileResponse:
    try:
        document_path = get_normative_document_path(document_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Неизвестный нормативный документ",
        ) from None

    if not document_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"PDF нормативного документа ещё не добавлен: {document_path.name}"
            ),
        )

    return FileResponse(
        document_path,
        media_type="application/pdf",
    )


app.mount(
    "/",
    StaticFiles(directory=FRONTEND_DIST, html=True),
    name="frontend",
)
