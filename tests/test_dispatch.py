import pytest
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


from ai_dispatch import dispatch_many


def test_dispatch_many_sends_all_commands():
    sent = []
    def fake_run(cmd, **kw):
        if "send-keys" in cmd:
            sent.append(cmd)
        return _run(0, stdout="line1\n<<<DONE>>>\n")
    with patch("subprocess.run", side_effect=fake_run):
        with patch("time.sleep"):
            dispatch_many([("task A", "", ""), ("task B", "gpt-4o", "http://localhost:8317")], session="ai-do")
    assert len(sent) == 2


def test_dispatch_many_returns_results_in_order():
    outputs = {"split-0": "result A\n<<<DONE>>>", "split-1": "result B\n<<<DONE>>>"}
    def fake_run(cmd, **kw):
        if "capture-pane" in cmd:
            window = cmd[3].split(":")[1]
            return _run(0, stdout=outputs.get(window, ""))
        return _run(0)
    with patch("subprocess.run", side_effect=fake_run):
        with patch("time.sleep"):
            results = dispatch_many([("task A", "", ""), ("task B", "", "")], session="ai-do")
    assert results[0].strip() == "result A"
    assert results[1].strip() == "result B"


def test_dispatch_many_sets_proxy_env_in_command():
    cmds = []
    def fake_run(cmd, **kw):
        if "send-keys" in cmd:
            cmds.append(cmd[4])  # cmd[4] is the text; cmd[3] is "-t target"
        return _run(0, stdout="<<<DONE>>>")
    with patch("subprocess.run", side_effect=fake_run):
        with patch("time.sleep"):
            dispatch_many([("do it", "gpt-4o", "http://localhost:8317")], session="ai-do")
    assert any("ANTHROPIC_BASE_URL" in c for c in cmds)
    assert any("gpt-4o" in c for c in cmds)


def test_dispatch_many_raises_on_timeout():
    def fake_run(cmd, **kw):
        return _run(0, stdout="still running")
    with patch("subprocess.run", side_effect=fake_run):
        with patch("time.sleep"):
            with patch("time.monotonic", side_effect=[0.0, 0.0, 99.0, 99.0]):
                with pytest.raises(TimeoutError):
                    dispatch_many([("task", "", "")], session="ai-do", timeout=1)


def test_dispatch_many_empty_list_returns_empty():
    assert dispatch_many([], session="ai-do") == []
