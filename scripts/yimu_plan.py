"""Validate AI-organized tasks and prepare exact API payloads without writing."""

from __future__ import annotations

import json
from dataclasses import dataclass

from yimu_api import Api, YimuError

MILLISECONDS_PER_MINUTE = 60_000
MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 1_440
PRIORITIES = range(4)
TEXT_BLOCK_TYPE = 1
INBOX_NAME = "收集箱"
TASK_FIELDS = frozenset({
    "title", "content", "project", "projectId", "level", "time",
    "startTime", "endTime", "reminder",
})


@dataclass(frozen=True)
class PreparedTask:
    task: dict
    notices: tuple[dict, ...]
    project_name: str


def nonempty_text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise YimuError(f"{field} 必须是非空字符串")
    return value.strip()


def nonnegative_int(value, field: str) -> int:
    if type(value) is not int or value < 0:
        raise YimuError(f"{field} 必须是非负整数")
    return value


def validate_item(item) -> dict:
    if not isinstance(item, dict):
        raise YimuError("任务条目必须是 JSON 对象")
    unknown = item.keys() - TASK_FIELDS
    if unknown:
        raise YimuError(f"不支持的字段: {', '.join(sorted(unknown))}")
    title = nonempty_text(item.get("title"), "title")
    if nonnegative_int(item.get("level", 0), "level") not in PRIORITIES:
        raise YimuError("level 必须在 0 到 3 之间")
    validate_optional_fields(item)
    if "reminder" in item:
        validate_reminder(item["reminder"])
    return {**item, "title": title}


def validate_optional_fields(item: dict) -> None:
    for field in ("time", "project", "projectId"):
        if field in item:
            nonempty_text(item[field], field)
    for field in ("startTime", "endTime"):
        if field in item:
            nonnegative_int(item[field], field)
    if "content" in item and not isinstance(item["content"], str):
        raise YimuError("content 必须是纯文本字符串，由 CLI 编码为一木富文本")
    if "time" in item and "startTime" in item:
        raise YimuError("time 与 startTime 二选一，避免覆盖时间意图")


def validate_reminder(reminder) -> None:
    if not isinstance(reminder, dict) or set(reminder) != {"beforeMinutes"}:
        raise YimuError('reminder 必须为 {"beforeMinutes": 非负整数}')
    nonnegative_int(reminder["beforeMinutes"], "reminder.beforeMinutes")


def validate_plan(items) -> list[dict]:
    if not isinstance(items, list) or not items:
        raise YimuError("计划必须是非空 JSON 数组")
    return [validate_item(item) for item in items]


def encode_content(text: str) -> str:
    blocks = [{
        "type": TEXT_BLOCK_TYPE, "textType": 0, "align": 0, "indent": 0,
        "number": 0, "position": 0, "quote": False, "check": False,
        "spanText": line, "spanList": [{
            "content": line, "color": 0, "fontSize": 0, "bold": False,
            "italic": False, "underlined": False, "strikethrough": False,
            "background": False, "backgroundColor": None,
        }],
    } for line in text.splitlines()]
    return json.dumps(blocks, ensure_ascii=False)


def project_candidates(item: dict, projects: list[dict]) -> list[dict]:
    if "projectId" in item:
        return [p for p in projects if str(p["projectId"]) == item["projectId"]]
    return [p for p in projects if p["name"] == item.get("project", INBOX_NAME)]


def resolve_project(item: dict, projects: list[dict]) -> dict:
    project_id = item.get("projectId")
    name = item.get("project", INBOX_NAME)
    matches = project_candidates(item, projects)
    if len(matches) != 1:
        raise YimuError(f"项目 {project_id or name!r} 匹配到 {len(matches)} 项，请指定唯一项目 ID")
    project = matches[0]
    if project_id and "project" in item and item["project"] != project["name"]:
        raise YimuError("project 与 projectId 指向不同项目")
    if project["projectType"] != 0:
        raise YimuError(f"{project['name']} 是聚合视图，请选择真实项目")
    return project


def resolve_times(api: Api, item: dict, now_ms: int) -> tuple[int, int]:
    start = item.get("startTime", now_ms)
    end = item.get("endTime", 0)
    if "time" in item:
        data = api.call("NLP_CHINESE_TIME_RECOGNITION", {"text": item["time"]})
        if not isinstance(data, dict) or not data.get("startTime"):
            raise YimuError(f"无法解析时间: {item['time']}")
        start = nonnegative_int(data["startTime"], "NLP.startTime")
        end = item.get("endTime", data.get("endTime") or 0)
    nonnegative_int(end, "endTime")
    if end and end < start:
        raise YimuError("endTime 早于 startTime")
    return start, end


def prepare_notice(item: dict, start: int) -> tuple[dict, ...]:
    if "reminder" not in item:
        return ()
    if not (item.get("startTime") or item.get("time")):
        raise YimuError("提醒需要明确的 startTime 或 time")
    minutes = item["reminder"]["beforeMinutes"]
    notice_time = start - minutes * MILLISECONDS_PER_MINUTE
    if notice_time <= 0:
        raise YimuError("提醒时间必须大于 0")
    days, remainder = divmod(minutes, MINUTES_PER_DAY)
    hours, minutes_part = divmod(remainder, MINUTES_PER_HOUR)
    return ({
        "mode": 1, "day": days, "hour": hours, "minute": minutes_part,
        "time": notice_time, "self": True,
        "msg": "准时提醒" if minutes == 0 else f"提前{minutes}分钟",
    },)


def prepare_task(api: Api, item: dict, context: dict) -> PreparedTask:
    project = resolve_project(item, context["projects"])
    start, end = resolve_times(api, item, context["now_ms"])
    notices = prepare_notice(item, start)
    params = {
        "title": item["title"], "projectIdStr": str(project["projectId"]),
        "taskType": 0, "level": item.get("level", 0),
        "startTime": start, "endTime": end, "positionWeight": 0,
        "isTop": False, "giveUp": False, "completeTime": 0,
        "noticeInfo": json.dumps({
            "appNotice": bool(notices), "emailAddress": "", "noticeWechat": False,
        }),
    }
    if "content" in item:
        params = {**params, "content": encode_content(item["content"])}
    return PreparedTask(params, notices, project["name"])


def prepare_plan(api: Api, items, now_ms: int) -> tuple[PreparedTask, ...]:
    validated = validate_plan(items)
    sync = api.call("TODO_SYNC_PAGE", {"gmtModified": 0})
    context = {"projects": sync["projectDTOS"], "now_ms": now_ms}
    return tuple(prepare_task(api, item, context) for item in validated)
