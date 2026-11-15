import json
import os

import requests


API_URL = os.getenv(
    "ESPD_LLM_API_URL",
    "http://192.168.3.30:8081/v1/chat/completions",
)
MODEL = os.getenv(
    "ESPD_LLM_MODEL",
    "saiga_yandexgpt_8b.Q8_0.gguf",
)
REQUEST_TIMEOUT = int(os.getenv("ESPD_LLM_TIMEOUT", "600"))


def request_ai_result(payload: dict) -> tuple[dict, dict]:
    response = requests.post(
        API_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Сервер модели вернул HTTP {response.status_code}: {response.text}"
        )

    response_data = response.json()

    try:
        raw_result = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(
            "Ответ сервера модели не содержит текст результата"
        ) from error

    try:
        ai_result = json.loads(raw_result)
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError(
            "Сервер модели вернул некорректный JSON результата"
        ) from error

    usage = response_data.get("usage", {})

    return ai_result, usage
