"""Execute prepared mutations and verify stored task and reminder data."""

from __future__ import annotations

import json

import requests

from yimu_api import Api, YimuError
from yimu_plan import PreparedTask, encode_content, nonempty_text

NOTICE_FIELDS = ("taskNoticeId", "mode", "day", "hour", "minute", "time", "msg", "self")
PRESERVED_SCHEDULE_FIELDS = ("startTime", "endTime", "noticeInfo")
IDENTITY_FIELDS = frozenset({"taskId", "taskIdStr", "method", "systemType"})


def task_notices(api: Api, task_id: str) -> list[dict]:
    data = api.call("TODO_SYNC_PAGE", {"gmtModified": 0})
    return [n for n in data["taskNotices"] if str(n["taskId"]) == task_id]


def notice_snapshot(notices: list[dict]) -> list[dict]:
    values = [{k: notice[k] for k in NOTICE_FIELDS} for notice in notices]
    return sorted(values, key=lambda n: str(n["taskNoticeId"]))


def get_task(api: Api, task_id: str) -> dict:
    task = api.call("TODO_TASK_GET_BY_ID", {"id": task_id})
    if not isinstance(task, dict) or str(task.get("taskId")) != task_id:
        raise YimuError(f"无法回读任务 {task_id}")
    return task


def comparable(field: str, value):
    if field in {"content", "noticeInfo"} and isinstance(value, str) and value:
        return json.loads(value)
    if field.endswith("IdStr"):
        return str(value)
    return value


def verify_fields(task: dict, expected: dict) -> None:
    mismatches = [key for key, value in expected.items()
                  if comparable(key, task.get(key)) != comparable(key, value)]
    if mismatches:
        raise YimuError(f"写入后字段不一致: {', '.join(mismatches)}")


def verify_notification_title(api: Api, task: dict) -> dict:
    recent = api.call("TODO_TASK_NOTICE_RECENT_QUERY", {})
    matches = [n for n in recent if str(n["taskId"]) == str(task["taskId"])]
    if any(n["title"] != task["title"] for n in matches):
        raise YimuError("最近提醒队列仍含旧标题，任务已写入，但提醒文案尚未验证通过")
    return {
        "text": task["title"], "source": "task.title",
        "recentQueueMatches": len(matches), "deliveryVerified": False,
    }


def result_id(value, field: str) -> str:
    if type(value) not in (str, int) or not str(value).isdigit():
        raise YimuError(f"写入响应未返回有效 {field}，结果未知；请先查询，勿重复提交")
    return str(value)


def verify_created_notices(api: Api, task_id: str, expected: list[dict]) -> None:
    actual = {str(n["taskNoticeId"]): n for n in task_notices(api, task_id)}
    for notice in expected:
        notice_id = notice["taskNoticeId"]
        if notice_id not in actual:
            raise YimuError(f"提醒 {notice_id} 创建后未能回读")
        fields = {k: v for k, v in notice.items() if k != "taskNoticeId"}
        verify_fields(actual[notice_id], fields)


def create_one(api: Api, prepared: PreparedTask) -> dict:
    journal = {"title": prepared.task["title"], "project": prepared.project_name}
    try:
        journal = {**journal, "stage": "create-task"}
        task_id = result_id(api.call("TODO_TASK_ADD_V2", prepared.task), "taskId")
        journal = {**journal, "taskId": task_id, "stage": "verify-task"}
        task = get_task(api, task_id)
        verify_fields(task, prepared.task)
        notices = []
        for notice in prepared.notices:
            journal = {**journal, "stage": "create-reminder"}
            params = {**notice, "taskIdStr": task_id}
            notice_id = result_id(api.call("TODO_TASK_NOTICE_ADD", params), "taskNoticeId")
            notices = [*notices, {**notice, "taskNoticeId": notice_id}]
            journal = {**journal, "noticeIds": [n["taskNoticeId"] for n in notices]}
        journal = {**journal, "stage": "verify-reminders"}
        if notices:
            verify_created_notices(api, task_id, notices)
        notification = verify_notification_title(api, task) if notices else None
        return {**journal, "ok": True, "stage": "verified", "notification": notification}
    except (YimuError, requests.RequestException, ValueError, KeyError) as exc:
        return {**journal, "ok": False, "error": str(exc), "retrySafe": False}


def execute_plan(api: Api, prepared: tuple[PreparedTask, ...]) -> dict:
    results = []
    for index, task in enumerate(prepared):
        result = create_one(api, task)
        results = [*results, result]
        if not result["ok"]:
            return {
                "ok": False, "results": results,
                "unattempted": [p.task["title"] for p in prepared[index + 1:]],
            }
    return {"ok": True, "results": results}


def prepare_update(fields: dict) -> dict:
    if not fields or fields.keys() & IDENTITY_FIELDS:
        raise YimuError("更新字段不能为空，也不能覆盖任务 ID 或协议字段")
    if "title" in fields:
        return {**fields, "title": nonempty_text(fields["title"], "title")}
    return dict(fields)


def verify_preserved_reminders(api: Api, task_id: str, original: list[dict]) -> None:
    if notice_snapshot(task_notices(api, task_id)) != original:
        raise YimuError("任务已更新，但原有提醒设置发生变化")


def update_task(api: Api, task_id: str, fields: dict) -> dict:
    expected = prepare_update(fields)
    before = get_task(api, task_id)
    renaming = "title" in expected
    preserve_schedule = renaming and not expected.keys() & set(PRESERVED_SCHEDULE_FIELDS)
    old_notices = notice_snapshot(task_notices(api, task_id)) if preserve_schedule else []
    journal = {"taskId": task_id, "stage": "update-task"}
    try:
        api.call("TODO_TASK_UPDATE", {**expected, "taskIdStr": task_id})
        journal = {**journal, "stage": "verify-task"}
        after = get_task(api, task_id)
        verify_fields(after, expected)
        if preserve_schedule:
            verify_fields(after, {k: before[k] for k in PRESERVED_SCHEDULE_FIELDS})
            verify_preserved_reminders(api, task_id, old_notices)
        notification = None
        if renaming:
            journal = {**journal, "stage": "verify-reminders"}
            notification = verify_notification_title(api, after)
        return {**journal, "ok": True, "stage": "verified", "notification": notification}
    except (YimuError, requests.RequestException, ValueError, KeyError) as exc:
        return {**journal, "ok": False, "error": str(exc), "retrySafe": False}


def rewrite_task(api: Api, task_id: str, options: dict) -> dict:
    fields = {"title": options["title"]}
    if options.get("content") is not None:
        fields = {**fields, "content": encode_content(options["content"])}
    return update_task(api, task_id, fields)
