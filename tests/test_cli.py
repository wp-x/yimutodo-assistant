import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

from support import NOW_MS, PROJECTS, ScriptedApi
from yimu_api import YimuError, normalize_cookie, parse_response
from yimutodo_cli import build_parser, dispatch

ROOT = Path(__file__).resolve().parent.parent
COMMAND_TIMEOUT_SECONDS = 10


class CliTests(unittest.TestCase):
    def test_dry_run_makes_only_read_calls(self):
        args = build_parser().parse_args(["add-task", "整理发票并提交报销", "--dry-run"])
        api = ScriptedApi([("TODO_SYNC_PAGE", {"projectDTOS": PROJECTS})])
        result = dispatch(api, args, NOW_MS)
        self.assertTrue(result["ok"])
        self.assertFalse(result["written"])
        self.assertEqual([method for method, _ in api.calls], ["TODO_SYNC_PAGE"])

    def test_validate_plan_needs_no_credentials(self):
        env = {**os.environ, "YIMUTODO_COOKIE": ""}
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/yimutodo_cli.py"), "validate-plan"],
            input='[{"title":"向小张发送会议纪要"}]', text=True,
            capture_output=True, env=env, timeout=COMMAND_TIMEOUT_SECONDS,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_invalid_plan_has_nonzero_exit_and_explicit_error(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/yimutodo_cli.py"), "validate-plan"],
            input='[{"title":null}]', text=True, capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["ok"])

    def test_cookie_prefix_compatibility_and_empty_values(self):
        self.assertEqual(normalize_cookie("Cookie: vertx-web.session=example"), "vertx-web.session=example")
        self.assertEqual(normalize_cookie("example"), "vertx-web.session=example")
        with self.assertRaises(YimuError):
            normalize_cookie("Cookie: ")

    def test_api_error_code_is_preserved(self):
        response = Mock()
        response.json.return_value = {"errorCode": 1000004, "errorMessage": "登录失效"}
        with self.assertRaisesRegex(YimuError, "1000004.*登录失效"):
            parse_response(response, "TODO_SYNC_PAGE")

    def test_invalid_cookie_error_does_not_echo_credential_value(self):
        credential = "private-example\r\nInvalid: header"
        with self.assertRaises(YimuError) as caught:
            normalize_cookie(credential)
        self.assertNotIn("private-example", str(caught.exception))

    def test_malformed_success_envelope_is_not_accepted(self):
        response = Mock()
        response.json.return_value = []
        with self.assertRaisesRegex(YimuError, "errorCode"):
            parse_response(response, "TODO_SYNC_PAGE")
