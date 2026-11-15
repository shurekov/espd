from pathlib import Path
from tempfile import TemporaryDirectory

from backend.docx_highlighter import highlight_document
from backend.pdf_converter import convert_docx_to_pdf


PREVIEW_STATUSES = {"fail", "review"}


def collect_preview_evidence(check_result: dict) -> list[str]:
    evidence_ids = []
    seen = set()

    for check in check_result.get("checks", []):
        if check.get("status") not in PREVIEW_STATUSES:
            continue

        for evidence_id in check.get("evidence", []):
            if evidence_id in seen:
                continue

            seen.add(evidence_id)
            evidence_ids.append(evidence_id)

    return evidence_ids


def build_document_preview(
    source_path: str | Path,
    output_path: str | Path,
    check_result: dict,
) -> dict:
    source = Path(source_path)
    output = Path(output_path)
    evidence_ids = collect_preview_evidence(check_result)

    output.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(
        prefix=".document-preview-",
        dir=output.parent,
    ) as temporary_directory:
        highlighted_path = Path(temporary_directory) / "highlighted.docx"

        matched_ids = highlight_document(
            source,
            highlighted_path,
            evidence_ids,
        )
        convert_docx_to_pdf(highlighted_path, output)

    return {
        "evidence_ids": evidence_ids,
        "highlighted_evidence_ids": [
            evidence_id for evidence_id in evidence_ids if evidence_id in matched_ids
        ],
        "unresolved_evidence_ids": [
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in matched_ids
        ],
    }
