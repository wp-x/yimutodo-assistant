import json
import unittest
from copy import deepcopy

from support import NOW_MS, PROJECTS, START_MS, ScriptedApi
from yimu_api import YimuError
from yimu_plan import encode_content, prepare_plan, resolve_project, validate_plan


class PlanTests(unittest.TestCase):
    def test_ai_title_and_multiline_notes_survive_encoding(self):
        title = "修订报价单并发送给王总"
        notes = "王总反馈报价偏高。\n调整价格后再发送。"
        items = [{"title": title, "content": notes}]
        original = deepcopy(items)
        api = ScriptedApi([("TODO_SYNC_PAGE", {"projectDTOS": PROJECTS})])
        prepared = prepare_plan(api, items, NOW_MS)[0]
        self.assertEqual(prepared.task["title"], title)
        blocks = json.loads(prepared.task["content"])
        self.assertEqual([b["spanList"][0]["content"] for b in blocks], notes.splitlines())
        self.assertEqual(items, original)
        self.assertEqual(prepared.notices, ())
        self.assertEqual(prepared.task["projectIdStr"], "91")
        self.assertFalse(json.loads(prepared.task["noticeInfo"])["appNotice"])

    def test_invalid_plan_is_rejected_before_api_access(self):
        cases = [None, [], ["原话"], [{"title": " "}], [{"title": 7}],
                 [{"title": "x", "level": True}], [{"title": "x", "level": 9}],
                 [{"title": "x", "startTime": "123"}],
                 [{"title": "x", "reminderText": "旧原话"}],
                 [{"title": "x", "content": []}],
                 [{"title": "x", "time": "明天", "startTime": START_MS}],
                 [{"title": "x", "reminder": {"beforeMinutes": -1}}]]
        for items in cases:
            with self.subTest(items=items):
                api = ScriptedApi([])
                with self.assertRaises(YimuError):
                    prepare_plan(api, items, NOW_MS)
                self.assertEqual(api.calls, [])

    def test_one_invalid_item_prevents_writing_earlier_valid_item(self):
        api = ScriptedApi([])
        with self.assertRaises(YimuError):
            prepare_plan(api, [{"title": "购买牛奶"}, {"title": None}], NOW_MS)
        self.assertEqual(api.calls, [])

    def test_duplicate_project_names_are_not_overwritten(self):
        projects = [*PROJECTS, {"projectId": 93, "name": "工作", "projectType": 0}]
        with self.assertRaisesRegex(YimuError, "2 项"):
            resolve_project({"project": "工作"}, projects)
        self.assertEqual(resolve_project({"projectId": "92"}, projects)["projectId"], 92)

    def test_missing_mismatched_and_virtual_projects_fail(self):
        projects = [*PROJECTS, {"projectId": 94, "name": "今天", "projectType": 1}]
        cases = [{"project": "不存在"}, {"projectId": "404"},
                 {"projectId": "91", "project": "工作"}, {"project": "今天"}]
        for item in cases:
            with self.subTest(item=item), self.assertRaises(YimuError):
                resolve_project(item, projects)

    def test_time_parser_never_overwrites_organized_title(self):
        api = ScriptedApi([
            ("TODO_SYNC_PAGE", {"projectDTOS": PROJECTS}),
            ("NLP_CHINESE_TIME_RECOGNITION", {"startTime": START_MS, "suggestText": "那个三点"}),
        ])
        item = {"title": "与小李核对合同", "time": "明天下午三点",
                "reminder": {"beforeMinutes": 10}}
        result = prepare_plan(api, [item], NOW_MS)[0]
        self.assertEqual(result.task["title"], item["title"])
        self.assertEqual(result.notices[0]["time"], START_MS - 600_000)
        self.assertEqual(result.notices[0]["msg"], "提前10分钟")
        self.assertTrue(json.loads(result.task["noticeInfo"])["appNotice"])

    def test_unrecognized_time_does_not_become_now(self):
        api = ScriptedApi([
            ("TODO_SYNC_PAGE", {"projectDTOS": PROJECTS}),
            ("NLP_CHINESE_TIME_RECOGNITION", {"suggestText": "有空"}),
        ])
        with self.assertRaisesRegex(YimuError, "无法解析时间"):
            prepare_plan(api, [{"title": "修订报价", "time": "有空"}], NOW_MS)

    def test_reminder_requires_explicit_time(self):
        api = ScriptedApi([("TODO_SYNC_PAGE", {"projectDTOS": PROJECTS})])
        with self.assertRaisesRegex(YimuError, "提醒需要明确"):
            prepare_plan(api, [{"title": "取快递", "reminder": {"beforeMinutes": 0}}], NOW_MS)

    def test_end_before_start_is_not_accepted(self):
        api = ScriptedApi([("TODO_SYNC_PAGE", {"projectDTOS": PROJECTS})])
        with self.assertRaisesRegex(YimuError, "早于"):
            prepare_plan(api, [{"title": "开会", "startTime": START_MS, "endTime": NOW_MS}], NOW_MS)

    def test_clear_notes_is_encoded_as_empty_document(self):
        self.assertEqual(json.loads(encode_content("")), [])

    def test_explicit_short_title_is_not_forced_into_a_template(self):
        self.assertEqual(validate_plan([{"title": "先活下来"}])[0]["title"], "先活下来")
