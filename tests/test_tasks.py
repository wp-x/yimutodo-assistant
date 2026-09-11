import unittest
from copy import deepcopy

import requests

from support import BASE_TASK, NOTICE, NOW_MS, PROJECTS, START_MS, ScriptedApi, stored_task
from yimu_api import YimuError
from yimu_plan import prepare_plan
from yimu_tasks import create_one, execute_plan, rewrite_task, update_task


def prepared_task(remind=False):
    item = {"title": "修订报价单并发送给王总", "startTime": START_MS}
    if remind:
        item = {**item, "reminder": {"beforeMinutes": 10}}
    api = ScriptedApi([("TODO_SYNC_PAGE", {"projectDTOS": PROJECTS})])
    return prepare_plan(api, [item], NOW_MS)[0]


def rename_steps(recent_title, *, notices_after=None):
    title = "修订报价单并发送给王总"
    return [
        ("TODO_TASK_GET_BY_ID", BASE_TASK),
        ("TODO_SYNC_PAGE", {"taskNotices": [NOTICE]}),
        ("TODO_TASK_UPDATE", True),
        ("TODO_TASK_GET_BY_ID", {**BASE_TASK, "title": title}),
        ("TODO_SYNC_PAGE", {"taskNotices": [NOTICE] if notices_after is None else notices_after}),
        ("TODO_TASK_NOTICE_RECENT_QUERY", [{"taskId": 42, "title": recent_title}]),
    ]


class ExecutionTests(unittest.TestCase):
    def test_rename_preserves_notice_rule_and_channels(self):
        title = "修订报价单并发送给王总"
        options = {"title": title}
        original = deepcopy(options)
        api = ScriptedApi(rename_steps(title))
        result = rewrite_task(api, "42", options)
        self.assertTrue(result["ok"])
        self.assertEqual(options, original)
        self.assertEqual(api.calls[2][1], {"taskIdStr": "42", "title": title})
        self.assertEqual(result["notification"]["text"], title)
        self.assertEqual(result["notification"]["recentQueueMatches"], 1)
        self.assertFalse(result["notification"]["deliveryVerified"])
        writes = [m for m, _ in api.calls if "ADD" in m or "DELETE" in m]
        self.assertEqual(writes, [])

    def test_stale_notification_title_is_a_visible_partial_failure(self):
        api = ScriptedApi(rename_steps("那个报价弄一下"))
        result = update_task(api, "42", {"title": "修订报价单并发送给王总"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["taskId"], "42")
        self.assertEqual(result["stage"], "verify-reminders")
        self.assertIn("旧标题", result["error"])

    def test_missing_recent_entry_does_not_claim_delivery(self):
        steps = rename_steps("unused")[:-1]
        api = ScriptedApi([*steps, ("TODO_TASK_NOTICE_RECENT_QUERY", [])])
        result = rewrite_task(api, "42", {"title": "修订报价单并发送给王总"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["notification"]["recentQueueMatches"], 0)
        self.assertFalse(result["notification"]["deliveryVerified"])

    def test_renaming_detects_accidental_reminder_removal(self):
        api = ScriptedApi(rename_steps("unused", notices_after=[]))
        result = rewrite_task(api, "42", {"title": "修订报价单并发送给王总"})
        self.assertFalse(result["ok"])
        self.assertIn("提醒设置发生变化", result["error"])

    def test_create_stores_final_title_and_time_rule_separately(self):
        prepared = prepared_task(remind=True)
        task = stored_task(prepared.task)
        notice = {**prepared.notices[0], "taskNoticeId": 80, "taskId": 42}
        api = ScriptedApi([
            ("TODO_TASK_ADD_V2", 42), ("TODO_TASK_GET_BY_ID", task),
            ("TODO_TASK_NOTICE_ADD", 80), ("TODO_SYNC_PAGE", {"taskNotices": [notice]}),
            ("TODO_TASK_NOTICE_RECENT_QUERY", [{"taskId": 42, "title": task["title"]}]),
        ])
        result = create_one(api, prepared)
        self.assertTrue(result["ok"])
        self.assertEqual(api.calls[0][1]["title"], "修订报价单并发送给王总")
        self.assertEqual(api.calls[2][1]["msg"], "提前10分钟")
        self.assertEqual(result["noticeIds"], ["80"])

    def test_reminder_failure_retains_task_id_and_stops_batch(self):
        prepared = prepared_task(remind=True)
        api = ScriptedApi([
            ("TODO_TASK_ADD_V2", 42), ("TODO_TASK_GET_BY_ID", stored_task(prepared.task)),
            ("TODO_TASK_NOTICE_ADD", requests.Timeout("notice request timed out")),
        ])
        result = execute_plan(api, (prepared, prepared))
        self.assertFalse(result["ok"])
        self.assertEqual(result["results"][0]["taskId"], "42")
        self.assertEqual(result["results"][0]["stage"], "create-reminder")
        self.assertEqual(len(result["unattempted"]), 1)
        self.assertEqual(len(api.calls), 3)

    def test_task_readback_mismatch_is_not_success(self):
        prepared = prepared_task()
        stored = {**stored_task(prepared.task), "title": "原话"}
        api = ScriptedApi([("TODO_TASK_ADD_V2", 42), ("TODO_TASK_GET_BY_ID", stored)])
        result = create_one(api, prepared)
        self.assertFalse(result["ok"])
        self.assertIn("title", result["error"])
        self.assertEqual(result["taskId"], "42")

    def test_lost_create_response_is_not_retried(self):
        api = ScriptedApi([("TODO_TASK_ADD_V2", requests.Timeout("timed out"))])
        result = create_one(api, prepared_task())
        self.assertFalse(result["ok"])
        self.assertFalse(result["retrySafe"])
        self.assertNotIn("taskId", result)
        self.assertEqual(len(api.calls), 1)

    def test_update_cannot_redirect_to_a_different_task(self):
        api = ScriptedApi([])
        with self.assertRaises(YimuError):
            update_task(api, "42", {"taskIdStr": "99", "title": "x"})
        self.assertEqual(api.calls, [])

    def test_completion_may_advance_a_repeating_tasks_schedule(self):
        after = {**BASE_TASK, "completeTime": NOW_MS, "startTime": START_MS + 86_400_000}
        api = ScriptedApi([
            ("TODO_TASK_GET_BY_ID", BASE_TASK), ("TODO_TASK_UPDATE", True),
            ("TODO_TASK_GET_BY_ID", after),
        ])
        result = update_task(api, "42", {"completeTime": NOW_MS})
        self.assertTrue(result["ok"])
