from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="ChatGPT Session Manager updater")
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)
    backup = target.with_name(f"{target.name}.bak")

    if not source.exists():
        raise FileNotFoundError(f"Downloaded update not found: {source}")
    if not target.exists():
        raise FileNotFoundError(f"Target executable not found: {target}")

    wait_for_process_exit(args.pid)
    if backup.exists():
        backup.unlink()
    shutil.copy2(target, backup)

    try:
        shutil.copy2(source, target)
    except Exception:
        if backup.exists():
            shutil.copy2(backup, target)
        raise

    subprocess.Popen([str(target)], close_fds=True)
    return 0


def wait_for_process_exit(pid: int, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_process_running(pid):
            return
        time.sleep(0.5)
    raise TimeoutError(f"Process did not exit before timeout: {pid}")


def is_process_running(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    return str(pid) in result.stdout


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
