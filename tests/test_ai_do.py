import sys
import pytest
from pathlib import Path
from unittest.mock import patch
from ai_do import load_yaml, route, get_model, get_model_cmd, dispatch_task
import ai_do


# ---------------------------------------------------------------------------
# load_yaml
# ---------------------------------------------------------------------------

def test_load_yaml_returns_dict(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("key: value\n")
    assert isinstance(load_yaml(f), dict)


def test_load_yaml_missing_file_returns_empty(tmp_path):
    assert load_yaml(tmp_path / "nonexistent.yaml") == {}


def test_load_yaml_models_schema(tmp_path):
    f = tmp_path / "models.yaml"
    f.write_text(
        "models:\n"
        "  claude:\n"
        "    model: claude-sonnet-4-6\n"
        "    proxy: \"\"\n"
        "    strengths: [architecture, reasoning]\n"
        "    failover: backup\n"
        "  gemini:\n"
        "    model: gemini-2.5-pro\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [large_context]\n"
    )
    result = load_yaml(f)
    assert "models" in result
    assert "claude" in result["models"]
    assert result["models"]["claude"]["model"] == "claude-sonnet-4-6"
    assert result["models"]["gemini"]["proxy"] == "http://localhost:8317"


def test_load_yaml_routing_schema(tmp_path):
    f = tmp_path / "routing.yaml"
    f.write_text(
        "rules:\n"
        "  - match: [implement, generate]\n"
        "    primary: codex\n"
        "    fallback: claude\n"
        "  - match: [review, debug]\n"
        "    primary: claude\n"
        "    fallback: backup\n"
    )
    result = load_yaml(f)
    assert "rules" in result
    assert result["rules"][0]["primary"] == "codex"
    assert "implement" in result["rules"][0]["match"]


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------

RULES = [
    {"match": ["implement", "generate", "scaffold"], "primary": "codex", "fallback": "claude"},
    {"match": ["review", "debug", "fix", "security"], "primary": "claude", "fallback": "backup"},
    {"match": ["analyze", "large_context"], "primary": "gemini", "fallback": "km"},
    {"match": ["docs", "readme", "translate"], "primary": "glm", "fallback": "openrouter"},
]


def test_route_matches_first_keyword():
    primary, fallback = route("implement JWT auth", RULES)
    assert primary == "codex"
    assert fallback == "claude"


def test_route_matches_middle_keyword():
    primary, _ = route("please review the PR", RULES)
    assert primary == "claude"


def test_route_case_insensitive():
    primary, _ = route("IMPLEMENT the feature", RULES)
    assert primary == "codex"


def test_route_no_match_returns_default():
    primary, fallback = route("do something vague", RULES)
    assert primary == "claude"
    assert fallback == "backup"


def test_route_first_rule_wins():
    primary, _ = route("implement and review", RULES)
    assert primary == "codex"


def test_route_empty_task_returns_default():
    primary, fallback = route("", RULES)
    assert primary == "claude"
    assert fallback == "backup"


# ---------------------------------------------------------------------------
# get_model / get_model_cmd
# ---------------------------------------------------------------------------

MODELS = {
    "claude": {"model": "claude-sonnet-4-6", "proxy": "", "strengths": ["reasoning"], "failover": "backup"},
    "gemini": {"model": "gemini-2.5-pro", "proxy": "http://localhost:8317", "strengths": ["large_context"]},
    "codex":  {"model": "gpt-4o", "proxy": "http://localhost:8317", "strengths": ["code_gen"]},
}


def test_get_model_known():
    m = get_model("claude", MODELS)
    assert m is not None
    assert m["model"] == "claude-sonnet-4-6"


def test_get_model_unknown_returns_none():
    assert get_model("nonexistent", MODELS) is None


def test_get_model_cmd_known_with_proxy():
    alias, proxy = get_model_cmd("codex", MODELS)
    assert alias == "gpt-4o"
    assert proxy == "http://localhost:8317"


def test_get_model_cmd_known_direct():
    alias, proxy = get_model_cmd("claude", MODELS)
    assert alias == "claude-sonnet-4-6"
    assert proxy == ""


def test_get_model_cmd_unknown_returns_empty():
    alias, proxy = get_model_cmd("unknown", MODELS)
    assert alias == ""
    assert proxy == ""


# ---------------------------------------------------------------------------
# dispatch_task
# ---------------------------------------------------------------------------

def _make_yaml_files(tmp_path):
    models = tmp_path / "models.yaml"
    models.write_text(
        "models:\n"
        "  claude:\n"
        "    model: claude-sonnet-4-6\n"
        "    proxy: \"\"\n"
        "    strengths: [reasoning]\n"
        "  codex:\n"
        "    model: gpt-4o\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [code_gen]\n"
    )
    routing = tmp_path / "routing.yaml"
    routing.write_text(
        "rules:\n"
        "  - match: [implement, generate]\n"
        "    primary: codex\n"
        "    fallback: claude\n"
    )
    return models, routing


def test_dispatch_task_dry_run_prints_routing(tmp_path, capsys):
    models_path, routing_path = _make_yaml_files(tmp_path)
    dispatch_task("implement login", models_path=models_path, routing_path=routing_path, dry_run=True)
    out = capsys.readouterr().out
    assert "codex" in out
    assert "gpt-4o" in out


def test_dispatch_task_dry_run_does_not_call_dispatch(tmp_path):
    models_path, routing_path = _make_yaml_files(tmp_path)
    with patch("ai_do.ai_dispatch") as mock_dispatch:
        dispatch_task("implement login", models_path=models_path, routing_path=routing_path, dry_run=True)
    mock_dispatch.dispatch.assert_not_called()


def test_dispatch_task_calls_dispatch(tmp_path):
    models_path, routing_path = _make_yaml_files(tmp_path)
    with patch("ai_do.ai_dispatch") as mock_dispatch:
        mock_dispatch.dispatch.return_value = "done"
        result = dispatch_task("implement login", models_path=models_path, routing_path=routing_path)
    mock_dispatch.dispatch.assert_called_once()
    assert result == "done"


def test_dispatch_task_passes_model_alias_and_proxy(tmp_path):
    models_path, routing_path = _make_yaml_files(tmp_path)
    with patch("ai_do.ai_dispatch") as mock_dispatch:
        mock_dispatch.dispatch.return_value = "ok"
        dispatch_task("implement login", models_path=models_path, routing_path=routing_path)
    _, kwargs = mock_dispatch.dispatch.call_args
    assert kwargs.get("model_alias") == "gpt-4o"
    assert kwargs.get("proxy_url") == "http://localhost:8317"


def test_dispatch_task_force_model_overrides_routing(tmp_path):
    models_path, routing_path = _make_yaml_files(tmp_path)
    with patch("ai_do.ai_dispatch") as mock_dispatch:
        mock_dispatch.dispatch.return_value = "ok"
        dispatch_task("implement login", models_path=models_path, routing_path=routing_path, force_model="claude")
    _, kwargs = mock_dispatch.dispatch.call_args
    assert kwargs.get("model_alias") == "claude-sonnet-4-6"
    assert kwargs.get("proxy_url") == ""


def test_dispatch_task_no_match_defaults_to_claude(tmp_path):
    models_path, routing_path = _make_yaml_files(tmp_path)
    with patch("ai_do.ai_dispatch") as mock_dispatch:
        mock_dispatch.dispatch.return_value = "ok"
        dispatch_task("something unrelated", models_path=models_path, routing_path=routing_path)
    mock_dispatch.dispatch.assert_called_once()


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------

def _run_cli(argv):
    old = sys.argv
    sys.argv = ["ai-do"] + argv
    try:
        try:
            ai_do.main()
        except SystemExit:
            pass
    finally:
        sys.argv = old


def test_cli_no_args_exits_nonzero():
    old = sys.argv
    sys.argv = ["ai-do"]
    try:
        with pytest.raises(SystemExit) as exc_info:
            ai_do.main()
        assert exc_info.value.code != 0
    finally:
        sys.argv = old


def test_cli_run_calls_dispatch_task():
    with patch("ai_do.dispatch_task", return_value="result") as mock_dt:
        _run_cli(["run", "implement auth"])
    mock_dt.assert_called_once()
    args, _ = mock_dt.call_args
    assert args[0] == "implement auth"


def test_cli_dry_run_flag():
    with patch("ai_do.dispatch_task", return_value="") as mock_dt:
        _run_cli(["run", "implement auth", "--dry-run"])
    _, kwargs = mock_dt.call_args
    assert kwargs.get("dry_run") is True


def test_cli_model_flag():
    with patch("ai_do.dispatch_task", return_value="ok") as mock_dt:
        _run_cli(["run", "implement auth", "--model", "gemini"])
    _, kwargs = mock_dt.call_args
    assert kwargs.get("force_model") == "gemini"


def test_cli_session_flag():
    with patch("ai_do.dispatch_task", return_value="ok") as mock_dt:
        _run_cli(["run", "some task", "--session", "my-session"])
    _, kwargs = mock_dt.call_args
    assert kwargs.get("session") == "my-session"


def test_cli_prints_result(capsys):
    with patch("ai_do.dispatch_task", return_value="the answer"):
        _run_cli(["run", "some task"])
    assert "the answer" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# dispatch_split
# ---------------------------------------------------------------------------

from ai_do import dispatch_split


def test_dispatch_split_routes_each_task(tmp_path):
    models_path, routing_path = _make_yaml_files(tmp_path)
    with patch("ai_do.ai_dispatch") as mock_dispatch:
        mock_dispatch.dispatch_many.return_value = ["ok1", "ok2"]
        results = dispatch_split(
            ["implement login", "implement logout"],
            models_path=models_path,
            routing_path=routing_path,
        )
    mock_dispatch.dispatch_many.assert_called_once()
    subtasks = mock_dispatch.dispatch_many.call_args[0][0]
    assert len(subtasks) == 2
    assert results == ["ok1", "ok2"]


def test_dispatch_split_passes_model_alias(tmp_path):
    models_path, routing_path = _make_yaml_files(tmp_path)
    with patch("ai_do.ai_dispatch") as mock_dispatch:
        mock_dispatch.dispatch_many.return_value = ["ok"]
        dispatch_split(["implement auth"], models_path=models_path, routing_path=routing_path)
    subtasks = mock_dispatch.dispatch_many.call_args[0][0]
    _, alias, proxy = subtasks[0]
    assert alias == "gpt-4o"
    assert proxy == "http://localhost:8317"


def test_cli_split_flag_parses_comma_separated(capsys):
    with patch("ai_do.dispatch_split", return_value=["r1", "r2"]) as mock_split:
        _run_cli(["run", "implement login,implement logout", "--split"])
    mock_split.assert_called_once()
    tasks = mock_split.call_args[0][0]
    assert tasks == ["implement login", "implement logout"]


def test_cli_split_prints_indexed_results(capsys):
    with patch("ai_do.dispatch_split", return_value=["result A", "result B"]):
        _run_cli(["run", "task1,task2", "--split"])
    out = capsys.readouterr().out
    assert "[0]" in out and "result A" in out
    assert "[1]" in out and "result B" in out


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------

from ai_do import notify


def test_notify_no_op_when_no_webhook(monkeypatch):
    monkeypatch.delenv("AI_NOTIFY_WEBHOOK", raising=False)
    with patch("urllib.request.urlopen") as mock_open:
        notify("hello")
    mock_open.assert_not_called()


def test_notify_telegram(monkeypatch):
    monkeypatch.setenv("AI_NOTIFY_WEBHOOK", "telegram:MYTOKEN:12345")
    with patch("ai_do._urllib.urlopen") as mock_open:
        notify("task done")
    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    assert "api.telegram.org" in req.full_url
    assert b"12345" in req.data


def test_notify_discord_webhook(monkeypatch):
    monkeypatch.setenv("AI_NOTIFY_WEBHOOK", "https://discord.com/api/webhooks/123/abc")
    with patch("ai_do._urllib.urlopen") as mock_open:
        notify("task done")
    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    assert "discord.com" in req.full_url


def test_notify_silently_ignores_errors(monkeypatch):
    monkeypatch.setenv("AI_NOTIFY_WEBHOOK", "https://discord.com/api/webhooks/x")
    with patch("ai_do._urllib.urlopen", side_effect=OSError("network error")):
        notify("task done")
