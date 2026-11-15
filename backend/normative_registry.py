import json
from pathlib import Path

from backend.profile_registry import get_profile


BASE_DIR = Path(__file__).resolve().parent.parent
NORMATIVE_ROOT = BASE_DIR / "normative"

NORMATIVE_DOCUMENTS = {
    "gost-19.507-79": {
        "standard": "ГОСТ 19.507-79",
        "filename": "gost-19.507-79.pdf",
    },
    "gost-19.503-79": {
        "standard": "ГОСТ 19.503-79",
        "filename": "gost-19.503-79.pdf",
    },
    "gost-19.505-79": {
        "standard": "ГОСТ 19.505-79",
        "filename": "gost-19.505-79.pdf",
    },
    "gost-19.402-78": {
        "standard": "ГОСТ 19.402-78",
        "filename": "gost-19.402-78.pdf",
    },
}

PROFILE_DOCUMENT_IDS = {
    "ved": "gost-19.507-79",
    "rsp": "gost-19.503-79",
    "rop": "gost-19.505-79",
    "opr": "gost-19.402-78",
}

RULE_PAGES: dict[str, int] = {
    "VED-01": 1,
    "VED-02": 1,
    "VED-03": 3,
    "VED-04": 3,
    "VED-05": 2,
    "VED-06": 2,
}


def get_normative_document_path(document_id: str) -> Path:
    document = NORMATIVE_DOCUMENTS[document_id]
    return NORMATIVE_ROOT / document["filename"]


def build_profile_normative(profile_id: str) -> dict:
    document_id = PROFILE_DOCUMENT_IDS[profile_id]
    document = NORMATIVE_DOCUMENTS[document_id]
    profile = get_profile(profile_id)

    normative_profile = json.loads(profile.rules_path.read_text(encoding="utf-8"))

    return {
        "document": {
            "id": document_id,
            "standard": document["standard"],
            "pdf_url": (f"/api/normative-documents/{document_id}.pdf"),
        },
        "rules": {
            rule["id"]: {
                "source": rule["source"],
                "requirement": rule["requirement"],
                "page": RULE_PAGES.get(rule["id"]),
            }
            for rule in normative_profile["rules"]
        },
    }
