# ai-dispatch Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the minimal dispatcher — one command string routes to a named tmux pane running `claude -p`, captures output, and returns it.

**Architecture:** Single stdlib-only script `src/ai_dispatch.py`. Wraps `tmux` via `subprocess` to create a named session+pane, send a task via `tmux send-keys`, poll `tmux capture-pane` until a sentinel appears, return captured text. Optionally loads an `ai-profile` before dispatching. Env var `AI_DISPATCH_SESSION` overrides the default session name `ai-do`.

**Tech Stack:** Python 3.8+ (stdlib only, subprocess to tmux), tmux 3.x, `claude` CLI (`-p` non-interactive mode), pytest + `unittest.mock` for unit tests.

---

## Pre-flight

```bash
sudo apt-get install -y tmux
tmux -V
```

Expected: `tmux 3.2a` (or later). No other setup needed — tmux, `claude`, and `ccs` are already on PATH.

---

### Task 1: tmux primitives

**Files:**
- Create: `src/ai_dispatch.py`
- Create: `tests/test_dispatch.py`

The core problem: how to drive tmux from Python and know when a command inside a pane has finished. Strategy: append `&& echo '<<<DONE>>>'` (or `; echo '<<<DONE>>>'`) to every command sent, then poll `tmux capture-pane` until that sentinel appears.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dispatch.py
from unittest.mock import patch, call
from ai_dispatch import (
    tmux_has_session,
    tmux_new_session,
    tmux_has_window,
    tmux_new_window,
    tmux_send_keys,
    tmux_capture_pane,
)


def _run(returncode=0, stdout=""):
    import subprocess
    r = subprocess.CompletedProcess(args=[], returncode=returncode)
    r.stdout = stdout
    return r


def test_has_session_true():
    with patch("subprocess.run", return_value=_run(0)) as mock:
        assert tmux_has_session("ai-do") is True
        mock.assert_called_once_with(
            ["tmux", "has-session", "-t", "ai-do"],
            capture_output=True,
        )


def test_has_session_false():
    with patch("subprocess.run", return_value=_run(1)):
        assert tmux_has_session("ai-do") is False


def test_new_session():
    with patch("subprocess.run", return_value=_run(0)) as mock:
        tmux_new_session("ai-do")
        mock.assert_called_once_with(
            ["tmux", "new-session", "-d", "-s", "ai-do"],
            check=True,
        )


def test_has_window_true():
    with patch("subprocess.run", return_value=_run(0)) as mock:
        assert tmux_has_window("ai-do", "worker") is True
        mock.assert_called_once_with(
            ["tmux", "has-session", "-t", "ai-do:worker"],
            capture_output=True,
        )


def test_has_window_false():
    with patch("subprocess.run", return_value=_run(1)):
        assert tmux_has_window("ai-do", "worker") is False


def test_new_window():
    with patch("subprocess.run", return_value=_run(0)) as mock:
        tmux_new_window("ai-do", "worker")
        mock.assert_called_once_with(
            ["tmux", "new-window", "-t", "ai-do", "-n", "worker"],
            check=True,
        )


def test_send_keys():
    with patch("subprocess.run", return_value=_run(0)) as mock:
        tmux_send_keys("ai-do", "worker", "echo hello")
        mock.assert_called_once_with(
            ["tmux", "send-keys", "-t", "ai-do:worker", "echo hello", "Enter"],
            check=True,
        )


def test_capture_pane():
    with patch("subprocess.run", return_value=_run(0, stdout="line1\nline2\n")) as mock:
        result = tmux_capture_pane("ai-do", "worker", lines=100)
        assert result == "line1\nline2\n"
        mock.assert_called_once_with(
            ["tmux", "capture-pane", "-pt", "ai-do:worker", "-S", "-100"],
            capture_output=True,
            text=True,
        )
```

- [ ] **Step 2: Run to verify all fail**

```bash
cd /home/hung/Videos/temp-2
source .venv/bin/activate
pytest tests/test_dispatch.py -v
```

Expected: `ImportError` — `ai_dispatch` not defined yet.

- [ ] **Step 3: Implement primitives in src/ai_dispatch.py**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_dispatch.py -v
```

Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/ai_dispatch.py tests/test_dispatch.py
git commit -m "feat: add tmux primitive wrappers for ai-dispatch"
```

---

### Task 2: ensure_pane and run_in_pane

**Files:**
- Modify: `src/ai_dispatch.py`
- Modify: `tests/test_dispatch.py`

`ensure_pane` idempotently creates the session+window. `run_in_pane` sends a command, appends the sentinel `<<<DONE>>>`, then polls until it appears (or raises on timeout).

- [ ] **Step 1: Write failing tests**

Append to `tests/test_dispatch.py`:

```python
import time
from ai_dispatch import ensure_pane, run_in_pane, SENTINEL


def test_sentinel_value():
    assert SENTINEL == "<<<DONE>>>"


def test_ensure_pane_creates_session_and_window():
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["tmux", "has-session", "-t"] and ":" not in cmd[3]:
            return _run(1)
        if cmd[:3] == ["tmux", "has-session", "-t"] and ":" in cmd[3]:
            return _run(1)
        return _run(0)
    with patch("subprocess.run", side_effect=fake_run):
        ensure_pane("ai-do", "worker")
    cmds = [" ".join(c) for c in calls]
    assert any("new-session" in c for c in cmds)
    assert any("new-window" in c for c in cmds)


def test_ensure_pane_skips_existing():
    with patch("subprocess.run", return_value=_run(0)) as mock:
        ensure_pane("ai-do", "worker")
    cmds = [" ".join(c.args if hasattr(c, "args") else c) for c in mock.call_args_list]
    cmd_strings = [" ".join(c[0][0]) for c in mock.call_args_list]
    assert not any("new-session" in c for c in cmd_strings)
    assert not any("new-window" in c for c in cmd_strings)


def test_run_in_pane_sends_command_with_sentinel():
    captured = ["line1\nline2\n<<<DONE>>>\n"]
    idx = [0]
    def fake_run(cmd, **kwargs):
        if cmd[1] == "send-keys":
            return _run(0)
        if cmd[1] == "capture-pane":
            out = captured[min(idx[0], len(captured)-1)]
            idx[0] += 1
            return _run(0, stdout=out)
        return _run(0)
    with patch("subprocess.run", side_effect=fake_run):
        with patch("time.sleep"):
            result = run_in_pane("ai-do", "worker", "echo hello", timeout=5)
    assert "line1" in result
    assert "line2" in result


def test_run_in_pane_raises_on_timeout():
    def fake_run(cmd, **kwargs):
        if cmd[1] == "capture-pane":
            return _run(0, stdout="still running...\n")
        return _run(0)
    with patch("subprocess.run", side_effect=fake_run):
        with patch("time.sleep"):
            with patch("time.monotonic", side_effect=[0.0, 0.0, 99.0]):
                try:
                    run_in_pane("ai-do", "worker", "slow-cmd", timeout=1)
                    assert False, "expected TimeoutError"
                except TimeoutError:
                    pass
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_dispatch.py -k "sentinel or ensure_pane or run_in_pane" -v
```

Expected: all FAILED — `ensure_pane`, `run_in_pane`, `SENTINEL` not defined.

- [ ] **Step 3: Implement ensure_pane and run_in_pane**

Append to `src/ai_dispatch.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_dispatch.py -v
```

Expected: 13 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/ai_dispatch.py tests/test_dispatch.py
git commit -m "feat: add ensure_pane and run_in_pane with sentinel polling"
```

---

### Task 3: dispatch() — profile load + task send

**Files:**
- Modify: `src/ai_dispatch.py`
- Modify: `tests/test_dispatch.py`

`dispatch(task, profile, session)` optionally loads an ai-profile, ensures the pane exists, sends `claude -p "<task>"` into it, returns output.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_dispatch.py`:

```python
from ai_dispatch import dispatch


def test_dispatch_runs_claude_in_pane():
    with patch("ai_dispatch.ensure_pane") as mock_ensure:
        with patch("ai_dispatch.run_in_pane", return_value="answer text") as mock_run:
            result = dispatch("what is 2+2", session="ai-do")
    mock_ensure.assert_called_once_with("ai-do", "default")
    cmd = mock_run.call_args[0][2]
    assert "claude" in cmd
    assert "-p" in cmd
    assert "what is 2+2" in cmd
    assert result == "answer text"


def test_dispatch_with_profile_uses_window_name():
    with patch("ai_dispatch.ensure_pane") as mock_ensure:
        with patch("ai_dispatch.run_in_pane", return_value="ok") as mock_run:
            with patch("ai_dispatch.load_profile") as mock_load:
                dispatch("task", profile="fullstack", session="ai-do")
    mock_load.assert_called_once_with("fullstack")
    mock_ensure.assert_called_once_with("ai-do", "fullstack")


def test_dispatch_no_profile_skips_load():
    with patch("ai_dispatch.ensure_pane"):
        with patch("ai_dispatch.run_in_pane", return_value="ok"):
            with patch("ai_dispatch.load_profile") as mock_load:
                dispatch("task", session="ai-do")
    mock_load.assert_not_called()


def test_dispatch_escapes_single_quotes_in_task():
    with patch("ai_dispatch.ensure_pane"):
        with patch("ai_dispatch.run_in_pane", return_value="ok") as mock_run:
            dispatch("it's a test", session="ai-do")
    cmd = mock_run.call_args[0][2]
    assert "it's" not in cmd or cmd.count("'") % 2 == 0
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_dispatch.py -k "dispatch" -v
```

Expected: all FAILED — `dispatch`, `load_profile` not defined.

- [ ] **Step 3: Implement dispatch and load_profile**

Append to `src/ai_dispatch.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_dispatch.py -v
```

Expected: 17 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/ai_dispatch.py tests/test_dispatch.py
git commit -m "feat: implement dispatch() with optional profile load"
```

---

### Task 4: CLI entry point

**Files:**
- Modify: `src/ai_dispatch.py`
- Modify: `tests/test_dispatch.py`

CLI: `ai-dispatch run "<task>" [--profile <name>] [--session <name>]`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_dispatch.py`:

```python
import subprocess as _subprocess


def test_cli_run_dispatches_task(tmp_path):
    with patch("ai_dispatch.dispatch", return_value="42") as mock_dispatch:
        import ai_dispatch
        import sys as _sys
        old_argv = _sys.argv
        _sys.argv = ["ai-dispatch", "run", "what is 2+2"]
        try:
            try:
                ai_dispatch.main()
            except SystemExit:
                pass
        finally:
            _sys.argv = old_argv
        mock_dispatch.assert_called_once_with(
            "what is 2+2", profile="", session="ai-do"
        )


def test_cli_run_with_profile(capsys):
    with patch("ai_dispatch.dispatch", return_value="result text"):
        import ai_dispatch
        import sys as _sys
        old_argv = _sys.argv
        _sys.argv = ["ai-dispatch", "run", "task", "--profile", "fullstack"]
        try:
            try:
                ai_dispatch.main()
            except SystemExit:
                pass
        finally:
            _sys.argv = old_argv
    out = capsys.readouterr().out
    assert "result text" in out


def test_cli_no_args_exits_nonzero():
    import ai_dispatch
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["ai-dispatch"]
    try:
        try:
            ai_dispatch.main()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code != 0
    finally:
        _sys.argv = old_argv
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_dispatch.py -k "cli" -v
```

Expected: all FAILED — `main` not defined.

- [ ] **Step 3: Implement main()**

Append to `src/ai_dispatch.py`:

```python
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
```

- [ ] **Step 4: Run full suite**

```bash
pytest tests/ -v
```

Expected: 20 PASSED (13 existing + 3 new CLI + 4 dispatch = 20, adjust as needed based on actual count).

- [ ] **Step 5: Commit**

```bash
git add src/ai_dispatch.py tests/test_dispatch.py
git commit -m "feat: add ai-dispatch CLI entry point"
```

---

### Task 5: Smoke test (integration, manual)

**Files:**
- Create: `scripts/smoke-dispatch.sh`

This is a manual integration test, not automated. It requires a live tmux server and the `claude` CLI authenticated.

- [ ] **Step 1: Create smoke script**

```bash
#!/usr/bin/env bash
set -euo pipefail

SESSION="ai-do-smoke"
TASK="Reply with only the word PONG and nothing else."

echo "=== ai-dispatch smoke test ==="
echo ""
echo "1. Checking prerequisites..."
tmux -V
claude --version

echo ""
echo "2. Dispatching task to session '$SESSION'..."
source .venv/bin/activate
result=$(python src/ai_dispatch.py run "$TASK" --session "$SESSION")
echo "Result: $result"

echo ""
echo "3. Verifying output contains PONG..."
if echo "$result" | grep -qi "pong"; then
    echo "PASS: got expected response"
else
    echo "FAIL: response did not contain PONG"
    echo "Raw result: $result"
    exit 1
fi

echo ""
echo "4. Verifying tmux session exists..."
tmux has-session -t "$SESSION" && echo "PASS: session '$SESSION' exists"

echo ""
echo "5. Cleanup..."
tmux kill-session -t "$SESSION" 2>/dev/null || true
echo "Session killed."

echo ""
echo "=== Smoke test PASSED ==="
```

- [ ] **Step 2: Make executable and run**

```bash
chmod +x scripts/smoke-dispatch.sh
cd /home/hung/Videos/temp-2
./scripts/smoke-dispatch.sh
```

Expected output ends with `=== Smoke test PASSED ===`.

If `claude` is not authenticated, run `claude` interactively first to complete auth.

- [ ] **Step 3: Run full test suite with coverage**

```bash
source .venv/bin/activate
pytest --cov=src --cov-report=term-missing -q
```

Expected: all tests pass, coverage >= 80%.

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke-dispatch.sh
git commit -m "feat: add smoke-dispatch.sh integration test script"
```

---

## Pass criteria

| Check | Pass condition |
|---|---|
| Unit tests | All pass |
| Coverage | >= 80% across `src/` |
| Smoke test | `scripts/smoke-dispatch.sh` exits 0 |
| tmux session | `ai-do-smoke` created and then cleaned up |
| Task routing | `claude -p` output captured and printed to stdout |

---

## Self-review

**Spec coverage:**
- tmux primitives (has-session, new-session, has-window, new-window, send-keys, capture-pane) → Task 1 ✓
- Sentinel-based completion detection → Task 2 ✓
- Profile load before dispatch → Task 3 ✓
- Single-quote escaping in task strings → Task 3 ✓
- CLI `run <task> [--profile] [--session]` → Task 4 ✓
- End-to-end integration proof → Task 5 ✓

**Placeholder scan:** No TBDs, no "handle edge cases", all code blocks complete.

**Type consistency:** `tmux_capture_pane` returns `str` in Task 1 and is consumed as `str` in Task 2. `dispatch` returns `str` in Task 3, printed in Task 4. Consistent throughout.
