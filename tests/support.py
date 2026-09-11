"""Isolated protocol fixtures. Never imported by runtime modules."""

from copy import deepcopy

NOW_MS = 1_789_106_400_000
START_MS = 1_789_196_400_000
PROJECTS = [
    {"projectId": 91, "name": "收集箱", "projectType": 0},
    {"projectId": 92, "name": "工作", "projectType": 0},
]
BASE_TASK = {
    "taskId": 42, "taskIdStr": "42", "title": "那个报价弄一下",
    "startTime": START_MS, "endTime": 0, "content": "[]",
    "noticeInfo": '{"appNotice":true,"noticeWechat":true,"emailAddress":""}',
}
NOTICE = {
    "taskId": 42, "taskNoticeId": 80, "mode": 1, "day": 0, "hour": 0,
    "minute": 10, "time": START_MS - 600_000, "msg": "提前10分钟", "self": False,
}


class ScriptedApi:
    def __init__(self, steps):
        self.steps = iter(steps)
        self.calls = []

    def call(self, method, params, suffix=""):
        self.calls.append((method, deepcopy(params)))
        expected_method, response = next(self.steps)
        if method != expected_method:
            raise AssertionError(f"Expected {expected_method}, got {method}")
        if isinstance(response, Exception):
            raise response
        return deepcopy(response)

    def get(self, path):
        raise AssertionError(f"Unexpected HTTP GET: {path}")


def stored_task(params):
    return {**params, "taskId": 42, "taskIdStr": "42"}
