#!/usr/bin/env python3
"""一木清单执行器：接收 AI 整理后的任务；自身不调用语言模型。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import requests

from yimu_api import Api, YimuError, connect
from yimu_plan import PRIORITIES, prepare_plan, validate_plan
from yimu_tasks import execute_plan, rewrite_task, update_task

MILLISECONDS_PER_SECOND = 1_000
ERROR_EXIT_CODE = 1


def parse_json_object(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"无效 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("参数必须是 JSON 对象")
    return parsed


def add_read_parsers(subparsers) -> None:
    subparsers.add_parser("status", help="验证认证")
    subparsers.add_parser("projects", help="列出项目")
    tasks = subparsers.add_parser("tasks", help="查询任务")
    tasks.add_argument("--status", choices=("open", "completed", "all"), default="open")
    tasks.add_argument("--project-id")
    tasks.add_argument("--query")
    tasks.add_argument("--limit", type=int)
    nlp = subparsers.add_parser("nlp", help="仅解析时间；suggestText 不是整理后的标题")
    nlp.add_argument("text")
    for name in ("add-batch", "validate-plan"):
        batch = subparsers.add_parser(name, help="接收已整理的任务 JSON 数组")
        batch.add_argument("--file", default="-", help="默认从 stdin 读取")
        if name == "add-batch":
            batch.add_argument("--dry-run", action="store_true", help="解析并预览，不写入")


def add_create_parser(subparsers) -> None:
    add = subparsers.add_parser("add-task", help="保存整理后的单条标题")
    add.add_argument("title")
    add.add_argument("--project-id")
    add.add_argument("--project")
    add.add_argument("--content", help="纯文本备注")
    add.add_argument("--time", help="自然语言时间")
    add.add_argument("--start-time", type=int)
    add.add_argument("--end-time", type=int)
    add.add_argument("--level", type=int, choices=PRIORITIES, default=0)
    add.add_argument("--remind-before", type=int, help="提前分钟数；0 表示准时提醒")
    add.add_argument("--dry-run", action="store_true")


def add_update_parsers(subparsers) -> None:
    update = subparsers.add_parser("update-task", help="更新原始 API 字段并回读验证")
    update.add_argument("task_id")
    update.add_argument("--fields", required=True, type=parse_json_object)
    rewrite = subparsers.add_parser("rewrite-task", help="保存改写后的标题并核验提醒文案")
    rewrite.add_argument("task_id")
    rewrite.add_argument("title")
    rewrite.add_argument("--content", help="整理后的完整备注；省略时保留原备注")
    for name in ("complete", "uncomplete"):
        parser = subparsers.add_parser(name)
        parser.add_argument("task_id")
    delete = subparsers.add_parser("delete-task")
    delete.add_argument("task_id")
    delete.add_argument("--permanent", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_read_parsers(subparsers)
    add_create_parser(subparsers)
    add_update_parsers(subparsers)
    call = subparsers.add_parser("call", help="调用原始 API")
    call.add_argument("method")
    call.add_argument("--params", type=parse_json_object, default={})
    call.add_argument("--suffix", choices=("", "/public"), default="")
    return parser


def task_matches(task: dict, args: argparse.Namespace) -> bool:
    completed = bool(task.get("completeTime", 0))
    if args.status != "all" and completed != (args.status == "completed"):
        return False
    if args.project_id and str(task["projectId"]) != args.project_id:
        return False
    return not args.query or args.query.casefold() in task["title"].casefold()


def query_tasks(api: Api, args: argparse.Namespace) -> list[dict]:
    if args.limit is not None and args.limit < 0:
        raise YimuError("limit 不能为负数")
    tasks = api.call("TODO_SYNC_PAGE", {"gmtModified": 0})["tasks"]
    return [t for t in tasks if task_matches(t, args)][:args.limit]


def load_plan(path: str):
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def single_item(args: argparse.Namespace) -> dict:
    fields = {
        "title": args.title, "content": args.content, "project": args.project,
        "projectId": args.project_id, "startTime": args.start_time,
        "endTime": args.end_time, "time": args.time, "level": args.level,
    }
    item = {k: v for k, v in fields.items() if v is not None}
    if args.remind_before is not None:
        return {**item, "reminder": {"beforeMinutes": args.remind_before}}
    return item


def add_tasks(api: Api, args: argparse.Namespace, now_ms: int) -> dict:
    items = [single_item(args)] if args.command == "add-task" else load_plan(args.file)
    prepared = prepare_plan(api, items, now_ms)
    if args.dry_run:
        return {"ok": True, "written": False, "prepared": [asdict(p) for p in prepared]}
    return execute_plan(api, prepared)


def delete_task(api: Api, args: argparse.Namespace) -> dict:
    api.call("TODO_TASK_DELETE", {"taskIdStr": args.task_id, "completely": False})
    if args.permanent:
        api.call("TODO_TASK_DELETE", {"taskIdStr": args.task_id, "completely": True})
    return {"taskId": args.task_id, "deleted": True, "permanent": args.permanent}


def dispatch(api: Api, args: argparse.Namespace, now_ms: int):
    handlers = {
        "status": lambda: api.get("/api/v/atop/user/info"),
        "projects": lambda: api.call("TODO_SYNC_PAGE", {"gmtModified": 0})["projectDTOS"],
        "tasks": lambda: query_tasks(api, args),
        "add-task": lambda: add_tasks(api, args, now_ms),
        "add-batch": lambda: add_tasks(api, args, now_ms),
        "update-task": lambda: update_task(api, args.task_id, args.fields),
        "rewrite-task": lambda: rewrite_task(api, args.task_id, vars(args)),
        "complete": lambda: update_task(api, args.task_id, {"completeTime": now_ms, "giveUp": False}),
        "uncomplete": lambda: update_task(api, args.task_id, {"completeTime": 0, "giveUp": False}),
        "delete-task": lambda: delete_task(api, args),
        "nlp": lambda: api.call("NLP_CHINESE_TIME_RECOGNITION", {"text": args.text}),
        "call": lambda: api.call(args.method, args.params, args.suffix),
    }
    return handlers[args.command]()


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "validate-plan":
            result = {"ok": True, "written": False, "tasks": validate_plan(load_plan(args.file))}
        else:
            result = dispatch(connect(), args, int(time.time() * MILLISECONDS_PER_SECOND))
    except (YimuError, requests.RequestException, ValueError, OSError, KeyError) as exc:
        result = {"ok": False, "error": str(exc)}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    if isinstance(result, dict) and result.get("ok") is False:
        raise SystemExit(ERROR_EXIT_CODE)


if __name__ == "__main__":
    main()
