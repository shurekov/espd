import tempfile
from pathlib import Path
from zipfile import BadZipFile

import requests
from docx.opc.exceptions import PackageNotFoundError
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from check_document import check_document


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
MAX_FILE_SIZE = 10 * 1024 * 1024

app = FastAPI(title="ЕСПД Контроль")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "espd-control",
    }


@app.post("/api/check")
async def check_uploaded_document(
        file: UploadFile = File(...),
) -> dict:
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
        )

        return {
            "filename": file.filename,
            "result": result,
            "usage": usage,
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


app.mount(
    "/",
    StaticFiles(directory=FRONTEND_DIST, html=True),
    name="frontend",
)