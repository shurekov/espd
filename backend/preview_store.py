import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from threading import Lock
from time import monotonic
from uuid import uuid4

from backend.document_preview import build_document_preview


@dataclass(frozen=True)
class StoredPreview:
    document_path: Path
    expires_at: float


class PreviewStore:
    def __init__(
        self,
        root: str | Path | None = None,
        ttl_seconds: float = 3600,
    ) -> None:
        self.root = (
            Path(root) if root is not None else Path(gettempdir()) / "espd-previews"
        )
        self.ttl_seconds = ttl_seconds
        self._previews: dict[str, StoredPreview] = {}
        self._lock = Lock()

        self.root.mkdir(parents=True, exist_ok=True)

    def create_preview(
        self,
        source_path: str | Path,
        check_result: dict,
    ) -> dict:
        self._remove_expired()

        preview_id = uuid4().hex
        preview_directory = self.root / preview_id
        document_path = preview_directory / "document.pdf"

        preview_directory.mkdir(parents=False, exist_ok=False)

        try:
            metadata = build_document_preview(
                source_path,
                document_path,
                check_result,
            )
        except Exception:
            shutil.rmtree(preview_directory, ignore_errors=True)
            raise

        with self._lock:
            self._previews[preview_id] = StoredPreview(
                document_path=document_path,
                expires_at=monotonic() + self.ttl_seconds,
            )

        return {
            "preview_id": preview_id,
            "document_pdf_url": (f"/api/previews/{preview_id}/document.pdf"),
            **metadata,
        }

    def get_document_path(self, preview_id: str) -> Path:
        with self._lock:
            self._remove_expired_locked()

            preview = self._previews.get(preview_id)

            if preview is None or not preview.document_path.is_file():
                self._previews.pop(preview_id, None)
                raise KeyError(preview_id)

            return preview.document_path

    def _remove_expired(self) -> None:
        with self._lock:
            self._remove_expired_locked()

    def _remove_expired_locked(self) -> None:
        now = monotonic()
        expired_ids = [
            preview_id
            for preview_id, preview in self._previews.items()
            if preview.expires_at <= now
        ]

        for preview_id in expired_ids:
            preview = self._previews.pop(preview_id)
            shutil.rmtree(
                preview.document_path.parent,
                ignore_errors=True,
            )
