"""Authentication and HTTP transport; task logic receives an injected API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import requests

BASE_URL = "https://yimutodo.com"
API_PATH = "/api/v/atop"
TIMEOUT_SECONDS = 30
COOKIE_ENV_NAME = "YIMUTODO_COOKIE"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class YimuError(RuntimeError):
    """A visible input, protocol, or verification failure."""


class Api(Protocol):
    def call(self, method: str, params: dict, suffix: str = "") -> Any: ...
    def get(self, path: str) -> Any: ...


@dataclass(frozen=True)
class ClientConfig:
    cookie: str
    base_url: str = BASE_URL
    timeout_seconds: int = TIMEOUT_SECONDS


class YimuClient:
    def __init__(self, config: ClientConfig, session: requests.Session):
        self.config = config
        self.session = session

    def call(self, method: str, params: dict, suffix: str = "") -> Any:
        response = self.session.post(
            f"{self.config.base_url}{API_PATH}{suffix}",
            json={**params, "method": method, "systemType": "PC"},
            timeout=self.config.timeout_seconds,
        )
        return parse_response(response, method)

    def get(self, path: str) -> Any:
        response = self.session.get(
            f"{self.config.base_url}{path}", timeout=self.config.timeout_seconds
        )
        return parse_response(response, f"GET {path}")


def normalize_cookie(value: str) -> str:
    cookie = value.strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie.split(":", maxsplit=1)[1].strip()
    if not cookie:
        raise YimuError("YIMUTODO_COOKIE 为空")
    if "\r" in cookie or "\n" in cookie:
        raise YimuError("Cookie 必须为单行；请只填写 Cookie 请求头的值")
    return cookie if "=" in cookie else f"vertx-web.session={cookie}"


def load_cookie(env_file: Path = ENV_FILE) -> str:
    cookie = os.environ.get(COOKIE_ENV_NAME)
    if cookie is not None:
        return normalize_cookie(cookie)
    if not env_file.exists():
        raise YimuError(f"请设置 {COOKIE_ENV_NAME} 或创建 {env_file}")
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if key.strip() == COOKIE_ENV_NAME and separator:
            return normalize_cookie(value.strip().strip("'\""))
    raise YimuError(f"{env_file} 中缺少 {COOKIE_ENV_NAME}")


def connect(config: ClientConfig | None = None) -> YimuClient:
    config = config if config is not None else ClientConfig(cookie=load_cookie())
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cookie": config.cookie,
    })
    return YimuClient(config, session)


def parse_response(response: requests.Response, operation: str) -> Any:
    response.raise_for_status()
    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        raise YimuError(f"{operation}: 响应不是 JSON") from exc
    if not isinstance(payload, dict) or "errorCode" not in payload:
        raise YimuError(f"{operation}: 响应缺少 errorCode")
    if payload["errorCode"] != 0:
        raise YimuError(
            f"{operation}: errorCode={payload['errorCode']} "
            f"message={payload.get('errorMessage')}"
        )
    return payload.get("data")
