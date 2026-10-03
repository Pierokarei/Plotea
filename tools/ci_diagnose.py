"""Run a few tests on their own and publish their errors as annotations.

    python tools/ci_diagnose.py tests/test_a.py::test_x tests/test_b.py

For a CI runner whose log needs an account to read: the output of the
chosen tests - tracebacks included - is cut into GitHub annotations, which
anyone can read. Each test gets two minutes, so a hang shows its stack
instead of stalling the job.
"""
from __future__ import annotations

import os
import subprocess
import sys

CHUNK = 3500        # GitHub cuts an annotation a little beyond 4 KB
MAX_CHUNKS = 8


def main(tests: list[str]) -> int:
    command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
               "-o", "addopts=", "-q", "--tb=short", "--timeout=120",
               "--timeout-method=thread", *tests]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    output = (result.stdout + result.stderr).replace("\r", "")
    print(output)
    if os.environ.get("GITHUB_ACTIONS"):
        chunks = [output[i:i + CHUNK]
                  for i in range(0, len(output), CHUNK)][-MAX_CHUNKS:]
        for number, chunk in enumerate(chunks, start=1):
            body = chunk.replace("%", "%25").replace("\n", "%0A")
            print(f"::error title=diagnostic {number}/{len(chunks)}::{body}")
    return 0                       # a diagnostic informs, it does not fail


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
