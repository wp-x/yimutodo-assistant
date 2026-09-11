#!/usr/bin/env python3
"""Run isolated regression tests with the required 60-second hard timeout."""

import os
import subprocess
import sys
from pathlib import Path

TEST_TIMEOUT_SECONDS = 60
TIMEOUT_EXIT_CODE = 124
ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "scripts")}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=ROOT, env=env, timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print("后端测试超过 60 秒，已终止。", file=sys.stderr)
        raise SystemExit(TIMEOUT_EXIT_CODE)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
