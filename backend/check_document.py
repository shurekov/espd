import json
import sys
import os
from pathlib import Path
from time import perf_counter

import requests

from backend.docx_reader import read_docx
from backend.hybrid_result import combine_results
from backend.profile_registry import get_profile
from backend.result_validator import (
    validate_result,
)
from backend.schema_builder import build_result_schema
from backend.ai_requests import request_isolated_ai_results
from backend.fake_llm import request_fake_ai_result
from backend.llm_client import (
    MODEL,
    request_ai_result as request_real_ai_result,
)

request_ai_result = (
    request_fake_ai_result
    if os.getenv("ESPD_FAKE_LLM") == "1"
    else request_real_ai_result
)

BASE_DIR = Path(__file__).resolve().parent.parent


def load_json(filename: str | Path) -> dict:
    path = Path(filename)

    if not path.is_absolute():
        path = BASE_DIR / path

    return json.loads(path.read_text(encoding="utf-8"))


def save_json(filename: str, value: dict) -> None:
    (BASE_DIR / filename).write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def check_document(
    path: str | Path,
    save_outputs: bool = True,
    profile_id: str = "ved",
) -> tuple[dict, dict]:
    total_started = perf_counter()

    profile = get_profile(profile_id)

    stage_started = perf_counter()
    document_structure = read_docx(path)
    document_facts = profile.extract_structure(document_structure)

    ai_document, rule_facts = profile.build_payload(
        document_structure,
        document_facts,
    )

    normative_profile = load_json(profile.rules_path)

    print(
        f"[timing] Разбор DOCX и извлечение фактов: "
        f"{perf_counter() - stage_started:.2f} с"
    )

    stage_started = perf_counter()

    if profile.request_mode == "isolated":
        if profile.build_system_prompt is None or profile.build_rule_input is None:
            raise ValueError(f"Профиль {profile_id} не настроен для отдельных запросов")

        ai_result, usage = request_isolated_ai_results(
            document_structure=document_structure,
            ai_document=ai_document,
            rule_facts=rule_facts,
            normative_profile=normative_profile,
            model=MODEL,
            request_ai_result=request_ai_result,
            build_system_prompt=profile.build_system_prompt,
            build_rule_input=profile.build_rule_input,
            max_tokens=profile.max_tokens,
        )

    else:
        if profile.system_prompt is None:
            raise ValueError(f"Для профиля {profile_id} не задан системный prompt")

        result_schema = build_result_schema(normative_profile)

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": profile.system_prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "normative_profile": normative_profile,
                            "document_facts": document_facts,
                            "rule_facts": rule_facts,
                            "document": ai_document,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": profile.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{profile_id}_check",
                    "strict": True,
                    "schema": result_schema,
                },
            },
        }

        user_content = payload["messages"][1]["content"]

        print(
            "[payload] Размер пользовательского содержимого: "
            f"{len(user_content)} символов"
        )
        print(
            "[payload] Размер данных документа для ИИ: "
            f"{len(json.dumps(ai_document, ensure_ascii=False))} символов"
        )

        ai_result, usage = request_ai_result(payload)

    print(f"[timing] Запросы к модели: {perf_counter() - stage_started:.2f} с")
    print(f"[timing] Использование токенов: {usage}")

    stage_started = perf_counter()
    validate_result(
        ai_result,
        document_structure,
        normative_profile,
    )
    print(
        f"[timing] Техническая валидация ответа: {perf_counter() - stage_started:.2f} с"
    )

    if save_outputs:
        save_json("model_result.json", ai_result)

    stage_started = perf_counter()
    final_result = combine_results(
        ai_result,
        document_structure,
        normative_profile,
        profile_structure=document_facts,
    )
    print(
        f"[timing] Независимый контроль и объединение: "
        f"{perf_counter() - stage_started:.2f} с"
    )

    if save_outputs:
        save_json("final_result.json", final_result)

    print(f"[timing] Общее время проверки: {perf_counter() - total_started:.2f} с")

    return final_result, usage


def print_result(result: dict, usage: dict) -> None:
    for check in result["checks"]:
        evidence = ", ".join(check["evidence"])

        print(
            f"{check['rule_id']} {check['status']} | "
            f"{check['comment']} | "
            f"Доказательства: {evidence}"
        )

        if check["agreement"] is False:
            print(
                f"  ИИ: {check['ai']['status']}; контроль: {check['control']['status']}"
            )

    print(f"\nИтог: {result['summary']}")
    print(f"\nИспользовано токенов: {usage}")
    print(
        "\nОтвет ИИ сохранён в model_result.json; "
        "итоговый результат — в final_result.json"
    )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(
            "Использование: python -m backend.check_document "
            "<файл.docx> [ved|rsp|rop|opr]"
        )
        sys.exit(1)

    profile_id = sys.argv[2] if len(sys.argv) == 3 else "ved"

    try:
        final_result, token_usage = check_document(
            sys.argv[1],
            profile_id=profile_id,
        )
    except (
        requests.RequestException,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"Проверка не выполнена: {error}")
        sys.exit(1)

    print_result(final_result, token_usage)
