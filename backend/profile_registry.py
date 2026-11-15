from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from backend.profiles.opr.opr_control import run_opr_control
from backend.profiles.opr.opr_structure import extract_opr_structure
from backend.profiles.opr.payload_builder import (
    build_opr_diagnostics,
    build_opr_payload,
    build_opr_rule_input,
)
from backend.profiles.opr.prompt import build_opr_system_prompt
from backend.profiles.rop.prompt import build_rop_system_prompt
from backend.profiles.rop.rop_control import run_rop_control
from backend.profiles.rop.rop_structure import extract_rop_structure
from backend.profiles.rop.payload_builder import (
    build_rop_diagnostics,
    build_rop_payload,
    build_rop_rule_input,
)
from backend.profiles.rsp.prompt import build_rsp_system_prompt
from backend.profiles.rsp.rsp_control import run_rsp_control
from backend.profiles.rsp.rsp_structure import extract_rsp_structure
from backend.profiles.rsp.payload_builder import (
    build_rsp_diagnostics,
    build_rsp_payload,
    build_rsp_rule_input,
)
from backend.profiles.ved.control_checker import run_structural_control
from backend.profiles.ved.fact_extractor import extract_document_facts
from backend.profiles.ved.payload_builder import build_ved_payload
from backend.profiles.ved.prompt import VED_SYSTEM_PROMPT
from backend.profiles.ved.diagnostics import (
    build_diagnostics as build_ved_diagnostics,
)

BASE_DIR = Path(__file__).resolve().parent.parent

StructureExtractor = Callable[[dict], dict]
PayloadBuilder = Callable[[dict, dict], tuple[dict, dict]]
ControlRunner = Callable[[dict, dict | None], dict]
SystemPromptBuilder = Callable[[str], str]
RuleInputBuilder = Callable[[str, dict, dict], tuple[dict, dict]]
DiagnosticsBuilder = Callable[[dict, dict], dict]


@dataclass(frozen=True)
class ProfileDefinition:
    rules_path: Path
    extract_structure: StructureExtractor
    build_payload: PayloadBuilder
    run_control: ControlRunner
    build_diagnostics: DiagnosticsBuilder
    controlled_rules: frozenset[str]
    request_mode: Literal["single", "isolated"]
    system_prompt: str | None = None
    build_system_prompt: SystemPromptBuilder | None = None
    build_rule_input: RuleInputBuilder | None = None
    max_tokens: int = 400


PROFILES = {
    "ved": ProfileDefinition(
        rules_path=BASE_DIR / "backend/profiles/ved/rules_ved.json",
        extract_structure=extract_document_facts,
        build_payload=build_ved_payload,
        run_control=run_structural_control,
        build_diagnostics=build_ved_diagnostics,
        controlled_rules=frozenset(
            {
                "VED-01",
                "VED-03",
                "VED-04",
                "VED-05",
                "VED-06",
            }
        ),
        request_mode="single",
        system_prompt=VED_SYSTEM_PROMPT,
        max_tokens=1000,
    ),
    "rsp": ProfileDefinition(
        rules_path=BASE_DIR / "backend/profiles/rsp/rules_rsp.json",
        extract_structure=extract_rsp_structure,
        build_payload=build_rsp_payload,
        run_control=run_rsp_control,
        build_diagnostics=build_rsp_diagnostics,
        controlled_rules=frozenset(
            {
                "RSP-01",
                "RSP-02",
                "RSP-08",
            }
        ),
        request_mode="isolated",
        build_system_prompt=build_rsp_system_prompt,
        build_rule_input=build_rsp_rule_input,
    ),
    "rop": ProfileDefinition(
        rules_path=BASE_DIR / "backend/profiles/rop/rules_rop.json",
        extract_structure=extract_rop_structure,
        build_payload=build_rop_payload,
        run_control=run_rop_control,
        build_diagnostics=build_rop_diagnostics,
        controlled_rules=frozenset(
            {
                "ROP-01",
                "ROP-02",
                "ROP-06",
            }
        ),
        request_mode="isolated",
        build_system_prompt=build_rop_system_prompt,
        build_rule_input=build_rop_rule_input,
    ),
    "opr": ProfileDefinition(
        rules_path=BASE_DIR / "backend/profiles/opr/rules_opr.json",
        extract_structure=extract_opr_structure,
        build_payload=build_opr_payload,
        run_control=run_opr_control,
        build_diagnostics=build_opr_diagnostics,
        controlled_rules=frozenset(
            {
                "OPR-01",
                "OPR-02",
                "OPR-04",
            }
        ),
        request_mode="isolated",
        build_system_prompt=build_opr_system_prompt,
        build_rule_input=build_opr_rule_input,
    ),
}


def get_profile(profile_id: str) -> ProfileDefinition:
    try:
        return PROFILES[profile_id]
    except KeyError:
        raise ValueError(f"Неизвестный профиль: {profile_id}") from None
