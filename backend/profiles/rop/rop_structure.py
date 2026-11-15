import json
import sys
from pathlib import Path

from backend.docx_reader import read_docx
from backend.profiles.common_structure import (
    extract_sectioned_structure,
    normalize_text,
    is_main_heading_block,
)

INFO_HEADINGS = {
    "аннотация": "annotation",
    "содержание": "contents",
    "оглавление": "contents",
}

KNOWN_MAIN_HEADINGS = {
    "общие сведения о программе",
    "общие сведения",
    "назначение программы",
    "условия выполнения",
    "условия выполнения программы",
    "выполнение программы",
    "сообщения оператору",
    "перечень сокращений",
}

SUBORDINATE_HEADING_STYLES = {f"heading{level}" for level in range(2, 10)} | {
    f"заголовок{level}" for level in range(2, 10)
}


def is_main_heading(block: dict) -> bool:
    return is_main_heading_block(
        block,
        INFO_HEADINGS,
        KNOWN_MAIN_HEADINGS,
        SUBORDINATE_HEADING_STYLES,
    )


def extract_rop_structure(document_structure: dict) -> dict:
    return extract_sectioned_structure(
        document_structure,
        INFO_HEADINGS,
        is_main_heading,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Использование: python -m "
            "backend.profiles.rop.rop_structure "
            "<руководство.docx>"
        )
        sys.exit(1)

    document_structure = read_docx(Path(sys.argv[1]))
    result = extract_rop_structure(document_structure)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
