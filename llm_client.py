import os
import traceback
import uuid
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    httpx = None

try:
    import config
except ImportError:
    config = None


LLM_DEBUG = os.getenv("LLM_DEBUG", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _debug(message: str) -> None:
    if LLM_DEBUG:
        print(f"[LLM] {message}")


def _cfg(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Возвращает значение сначала из переменных окружения,
    затем из config.py, если он доступен.
    """
    value = os.getenv(name)
    if value is not None:
        return value

    if config is not None:
        return getattr(config, name, default)

    return default


def _get_ssl_verify() -> Any:
    """
    Возвращает:
    - путь к CA-бандлу, если задан GIGACHAT_CA_BUNDLE;
    - True/False в зависимости от GIGACHAT_VERIFY_SSL.

    По умолчанию проверка SSL отключена, чтобы локально проходить
    через корпоративные самоподписанные сертификаты.
    """
    ca_bundle = os.getenv("GIGACHAT_CA_BUNDLE", "").strip()
    if ca_bundle:
        return ca_bundle

    raw_value = os.getenv("GIGACHAT_VERIFY_SSL", "false").strip().lower()
    return raw_value not in {"false", "0", "no", "off"}


def ask_llm(user_prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """
    Единая точка вызова LLM.

    Возвращает текст ответа или None, если LLM недоступна.
    При ошибке всегда уходит в fallback, чтобы пайплайн продолжал работать.
    """
    provider = str(_cfg("LLM_PROVIDER", "fallback")).strip().lower()

    _debug(f"ask_llm called. provider={provider!r}")

    if provider == "gigachat":
        return _ask_gigachat_rest(user_prompt, system_prompt)

    _debug("Provider is not gigachat. Returning None.")
    return None


def _ask_gigachat_rest(user_prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """
    Прямой вызов GigaChat REST API через httpx.

    Это обходит проблему, когда официальный SDK не полностью
    применяет verify_ssl=False к авторизационному клиенту.
    """
    if httpx is None:
        _debug("httpx is not installed. Run: python -m pip install httpx")
        return None

    credentials = str(_cfg("GIGACHAT_CREDENTIALS", "")).strip()
    if not credentials:
        _debug("GIGACHAT_CREDENTIALS is empty.")
        return None

    model = str(_cfg("LLM_MODEL", "GigaChat-3-Ultra")).strip()

    try:
        temperature = float(_cfg("LLM_TEMPERATURE", "0.0"))
    except (TypeError, ValueError):
        temperature = 0.0

    auth_url = os.getenv(
        "GIGACHAT_AUTH_URL",
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    ).strip()

    chat_url = os.getenv(
        "GIGACHAT_CHAT_URL",
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    ).strip()

    scope = os.getenv(
        "GIGACHAT_SCOPE",
        "https://api.gigachat.ai/v1"
    ).strip()

    verify = _get_ssl_verify()

    _debug(
        "GigaChat REST settings: "
        f"auth_url={auth_url!r}, chat_url={chat_url!r}, "
        f"model={model!r}, temperature={temperature}, verify={verify!r}"
    )

    messages: List[Dict[str, str]] = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    messages.append({
        "role": "user",
        "content": user_prompt
    })

    try:
        # Если пользователь случайно вставил пару вида client_id:client_secret,
        # закодируем её в base64. Если уже дан base64-credential, используем как есть.
        basic_token = credentials
        if ":" in credentials:
            import base64
            basic_token = base64.b64encode(credentials.encode("utf-8")).decode("ascii")

        rq_uid = str(uuid.uuid4())

        auth_headers = {
            "Authorization": f"Basic {basic_token}",
            "RqUID": rq_uid,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        auth_payload = {
            "scope": scope
        }

        _debug("Requesting GigaChat access token...")

        token_response = httpx.post(
            auth_url,
            headers=auth_headers,
            data=auth_payload,
            verify=verify,
            timeout=30.0,
        )

        _debug(f"GigaChat auth status code: {token_response.status_code}")

        if token_response.status_code != 200:
            _debug(f"GigaChat auth failed. Response body: {token_response.text[:1000]}")
            return None

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            _debug(f"No access_token in auth response: {str(token_data)[:1000]}")
            return None

        _debug("Access token received.")

        chat_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        chat_payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        _debug("Sending chat request to GigaChat...")

        chat_response = httpx.post(
            chat_url,
            headers=chat_headers,
            json=chat_payload,
            verify=verify,
            timeout=60.0,
        )

        _debug(f"GigaChat chat status code: {chat_response.status_code}")

        if chat_response.status_code != 200:
            _debug(f"GigaChat chat request failed. Response body: {chat_response.text[:1000]}")
            return None

        chat_data = chat_response.json()

        try:
            content = chat_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            _debug(f"Unexpected GigaChat response structure: {str(chat_data)[:1000]}")
            return None

        if content:
            _debug("GigaChat returned content.")
            return content

        _debug("GigaChat returned empty content.")
        return None

    except Exception as e:
        _debug(f"GigaChat REST exception: {e}")
        if LLM_DEBUG:
            traceback.print_exc()
        return None