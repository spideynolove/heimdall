#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys


def tmux_has_session(session: str) -> bool:
    r = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
    return r.returncode == 0


def tmux_new_session(session: str) -> None:
    subprocess.run(["tmux", "new-session", "-d", "-s", session], check=True)


def tmux_has_window(session: str, window: str) -> bool:
    r = subprocess.run(
        ["tmux", "has-session", "-t", f"{session}:{window}"], capture_output=True
    )
    return r.returncode == 0


def tmux_new_window(session: str, window: str) -> None:
    subprocess.run(
        ["tmux", "new-window", "-t", session, "-n", window], check=True
    )


def tmux_send_keys(session: str, window: str, text: str) -> None:
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{session}:{window}", text, "Enter"], check=True
    )


def tmux_capture_pane(session: str, window: str, lines: int = 200) -> str:
    r = subprocess.run(
        ["tmux", "capture-pane", "-pt", f"{session}:{window}", "-S", f"-{lines}"],
        capture_output=True,
        text=True,
    )
    return r.stdout


import time

SENTINEL = "<<<DONE>>>"


def ensure_pane(session: str, window: str) -> None:
    if not tmux_has_session(session):
        tmux_new_session(session)
    if not tmux_has_window(session, window):
        tmux_new_window(session, window)


def run_in_pane(session: str, window: str, cmd: str, timeout: int = 120) -> str:
    tmux_send_keys(session, window, f"{cmd}; echo '{SENTINEL}'")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        output = tmux_capture_pane(session, window)
        if SENTINEL in output:
            lines = output.split("\n")
            result = []
            for line in lines:
                if SENTINEL in line:
                    break
                result.append(line)
            return "\n".join(result)
        time.sleep(1)
    raise TimeoutError(f"command in {session}:{window} did not complete within {timeout}s")


import os
from pathlib import Path


def load_profile(name: str) -> None:
    profiles_dir = Path(os.environ.get("AI_PROFILES_DIR", Path.home() / ".ai-profiles"))
    claude_dir = Path(os.environ.get("AI_CLAUDE_DIR", Path.home() / ".claude"))
    profile_dir = profiles_dir / name
    if not profile_dir.is_dir():
        print(f"warning: profile '{name}' not found, skipping load", file=sys.stderr)
        return
    sys.path.insert(0, str(Path(__file__).parent))
    from ai_profile import cmd_load
    cmd_load(name, profiles_dir, claude_dir)


def _escape(text: str) -> str:
    return text.replace("'", "'\\''")


def dispatch(task: str, profile: str = "", session: str = "ai-do") -> str:
    window = profile if profile else "default"
    if profile:
        load_profile(profile)
    ensure_pane(session, window)
    cmd = f"claude -p '{_escape(task)}'"
    return run_in_pane(session, window, cmd)


def main() -> None:
    session = os.environ.get("AI_DISPATCH_SESSION", "ai-do")
    args = sys.argv[1:]
    if not args or args[0] != "run":
        print("usage: ai-dispatch run <task> [--profile <name>] [--session <name>]", file=sys.stderr)
        sys.exit(1)
    args = args[1:]
    task = ""
    profile = ""
    i = 0
    while i < len(args):
        if args[i] == "--profile" and i + 1 < len(args):
            profile = args[i + 1]
            i += 2
        elif args[i] == "--session" and i + 1 < len(args):
            session = args[i + 1]
            i += 2
        elif not task:
            task = args[i]
            i += 1
        else:
            i += 1
    if not task:
        print("error: task string required", file=sys.stderr)
        sys.exit(1)
    result = dispatch(task, profile=profile, session=session)
    print(result)


if __name__ == "__main__":
    main()
