"""Run a few tests one by one and publish what each says as annotations.

    python tools/ci_diagnose.py tests/test_a.py::test_x tests/test_b.py

For a CI runner whose log needs an account to read: the output of each
chosen test - traceback included - becomes GitHub annotations, which anyone
can read. Each test runs in its own process, so one that crashes Qt cannot
take the others' reports with it, and gets two minutes, so a hang shows its
stack instead of stalling the job.
"""
from __future__ import annotations

import os
import subprocess
import sys

CHUNK = 3000        # GitHub cuts an annotation a little beyond 4 KB
PER_TEST = 2        # annotations kept per test: the end of its output


def run(test: str) -> str:
    command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
               "-o", "addopts=", "-q", "--tb=long", "-rA",
               "--timeout=120", "--timeout-method=thread", test]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    output = (result.stdout + result.stderr).replace("\r", "")
    return f"[code {result.returncode}] {test}\n{output}"


def main(tests: list[str]) -> int:
    for test in tests:
        output = run(test)
        print(output)
        if not os.environ.get("GITHUB_ACTIONS"):
            continue
        chunks = [output[i:i + CHUNK]
                  for i in range(0, len(output), CHUNK)][-PER_TEST:]
        name = test.rsplit("::", 1)[-1]
        for number, chunk in enumerate(chunks, start=1):
            body = chunk.replace("%", "%25").replace("\n", "%0A")
            print(f"::error title={name} {number}/{len(chunks)}::{body}")
        sys.stdout.flush()
    return 0                       # a diagnostic informs, it does not fail


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
