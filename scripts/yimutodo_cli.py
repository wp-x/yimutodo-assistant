#!/usr/bin/env python3
"""Command-line client for the unofficial yimutodo.com API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://yimutodo.com"
API_PATH = "/api/v/atop"
DEFAULT_PROJECT_ID = "128338"
DEFAULT_TIMEOUT_SECONDS = 30
COOKIE_ENV_NAME = "YIMUTODO_COOKIE"
SKILL_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = SKILL_ROOT / ".env"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class YimuError(RuntimeError):
    """Raised when the HTTP or Yimu API request fails."""


@dataclass(frozen=True)
class ClientConfig:
    cookie: str
    base_url: str = BASE_URL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


class YimuClient:
    def __init__(self, config: ClientConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Cookie": normalize_cookie(config.cookie),
        })

    def call(self, method: str, params: dict[str, Any], suffix: str = "") -> Any:
        body = {"method": method, "systemType": "PC", **params}
        response = self.session.post(
            f"{self.config.base_url}{API_PATH}{suffix}",
            json=body,
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
    if not cookie:
        raise YimuError("YIMUTODO_COOKIE 为空")
    if cookie.lower().startswith("cookie:"):
        cookie = cookie.split(":", maxsplit=1)[1].strip()
    if "=" not in cookie:
        return f"vertx-web.session={cookie}"
    return cookie


def load_cookie() -> str:
    environment_cookie = os.environ.get(COOKIE_ENV_NAME)
    if environment_cookie is not None:
        return normalize_cookie(environment_cookie)
    if not ENV_FILE.exists():
        raise YimuError(f"请设置 {COOKIE_ENV_NAME} 或创建 {ENV_FILE}")
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if key.strip() == COOKIE_ENV_NAME and separator:
            return normalize_cookie(value.strip().strip("'\""))
    raise YimuError(f"{ENV_FILE} 中缺少 {COOKIE_ENV_NAME}")


def parse_response(response: requests.Response, operation: str) -> Any:
    response.raise_for_status()
    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        raise YimuError(f"{operation}: 响应不是 JSON") from exc
    if payload.get("errorCode") != 0:
        raise YimuError(
            f"{operation}: errorCode={payload.get('errorCode')} "
            f"message={payload.get('errorMessage')}"
        )
    return payload.get("data")


def parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"无效 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("参数必须是 JSON 对象")
    return parsed


def add_common_subcommands(subparsers: Any) -> None:
    subparsers.add_parser("status", help="验证认证并返回当前用户信息")
    subparsers.add_parser("projects", help="列出项目")
    tasks = subparsers.add_parser("tasks", help="查询任务")
    tasks.add_argument("--status", choices=("open", "completed", "all"), default="open")
    tasks.add_argument("--project-id")
    tasks.add_argument("--query")
    tasks.add_argument("--limit", type=int)


def add_mutation_subcommands(subparsers: Any) -> None:
    add_task = subparsers.add_parser("add-task", help="创建普通任务")
    add_task.add_argument("title")
    add_task.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    add_task.add_argument("--start-time", type=int)
    add_task.add_argument("--end-time", type=int, default=0)
    add_task.add_argument("--level", type=int, choices=range(4), default=0)
    update = subparsers.add_parser("update-task", help="更新任务字段")
    update.add_argument("task_id")
    update.add_argument("--fields", required=True, type=parse_json_object)
    for name in ("complete", "uncomplete"):
        parser = subparsers.add_parser(name, help=f"{name} task")
        parser.add_argument("task_id")
    delete = subparsers.add_parser("delete-task", help="删除任务")
    delete.add_argument("task_id")
    delete.add_argument("--permanent", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_common_subcommands(subparsers)
    add_mutation_subcommands(subparsers)
    nlp = subparsers.add_parser("nlp", help="解析中文自然语言时间")
    nlp.add_argument("text")
    call = subparsers.add_parser("call", help="调用统一 method 分发接口")
    call.add_argument("method")
    call.add_argument("--params", type=parse_json_object, default={})
    call.add_argument("--suffix", choices=("", "/public"), default="")
    return parser


def task_matches(task: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.status == "open" and task.get("completeTime", 0):
        return False
    if args.status == "completed" and not task.get("completeTime", 0):
        return False
    if args.project_id and str(task.get("projectId")) != args.project_id:
        return False
    if args.query and args.query.casefold() not in str(task.get("title", "")).casefold():
        return False
    return True


def query_tasks(client: YimuClient, args: argparse.Namespace) -> list[dict[str, Any]]:
    tasks = client.call("TODO_SYNC_PAGE", {"gmtModified": 0}).get("tasks", [])
    matches = [task for task in tasks if task_matches(task, args)]
    return matches[: args.limit] if args.limit is not None else matches


def add_task(client: YimuClient, args: argparse.Namespace) -> Any:
    now_ms = int(time.time() * 1000)
    params = {
        "title": args.title,
        "projectIdStr": args.project_id,
        "taskType": 0,
        "level": args.level,
        "startTime": args.start_time if args.start_time is not None else now_ms,
        "endTime": args.end_time,
        "positionWeight": 0,
        "isTop": False,
        "giveUp": False,
        "completeTime": 0,
    }
    return client.call("TODO_TASK_ADD_V2", params)


def mutate_task(client: YimuClient, args: argparse.Namespace) -> Any:
    if args.command == "update-task":
        return client.call("TODO_TASK_UPDATE", {"taskIdStr": args.task_id, **args.fields})
    complete_time = int(time.time() * 1000) if args.command == "complete" else 0
    return client.call(
        "TODO_TASK_UPDATE",
        {"taskIdStr": args.task_id, "completeTime": complete_time, "giveUp": False},
    )


def delete_task(client: YimuClient, args: argparse.Namespace) -> dict[str, Any]:
    client.call("TODO_TASK_DELETE", {"taskIdStr": args.task_id, "completely": False})
    if args.permanent:
        client.call("TODO_TASK_DELETE", {"taskIdStr": args.task_id, "completely": True})
    return {"taskId": args.task_id, "deleted": True, "permanent": args.permanent}


def dispatch(client: YimuClient, args: argparse.Namespace) -> Any:
    if args.command == "status":
        return client.get("/api/v/atop/user/info")
    if args.command == "projects":
        return client.call("TODO_SYNC_PAGE", {"gmtModified": 0}).get("projectDTOS", [])
    if args.command == "tasks":
        return query_tasks(client, args)
    if args.command == "add-task":
        return add_task(client, args)
    if args.command in {"update-task", "complete", "uncomplete"}:
        return mutate_task(client, args)
    if args.command == "delete-task":
        return delete_task(client, args)
    if args.command == "nlp":
        return client.call("NLP_CHINESE_TIME_RECOGNITION", {"text": args.text})
    return client.call(args.method, args.params, args.suffix)


def main() -> None:
    args = build_parser().parse_args()
    result = dispatch(YimuClient(ClientConfig(cookie=load_cookie())), args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
