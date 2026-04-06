import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import ai_status


def test_fetch_proxy_stats_returns_dict():
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"requests": 42}).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = ai_status.fetch_proxy_stats("http://localhost:8317")
    assert result["requests"] == 42


def test_fetch_proxy_stats_returns_empty_on_error():
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        result = ai_status.fetch_proxy_stats("http://localhost:8317")
    assert result == {}


def test_show_models_prints_table(tmp_path, capsys):
    models = tmp_path / "models.yaml"
    models.write_text(
        "models:\n"
        "  claude:\n"
        "    model: claude-sonnet-4-6\n"
        "    proxy: \"\"\n"
        "  codex:\n"
        "    model: gpt-4o\n"
        "    proxy: http://localhost:8317\n"
    )
    ai_status.show_models(models)
    out = capsys.readouterr().out
    assert "claude" in out
    assert "codex" in out
    assert "gpt-4o" in out


def test_show_models_missing_file(tmp_path, capsys):
    ai_status.show_models(tmp_path / "nonexistent.yaml")
    assert "not found" in capsys.readouterr().out


def test_show_active_profiles(tmp_path, capsys):
    (tmp_path / ".active").write_text("base fullstack")
    ai_status.show_profiles(tmp_path)
    out = capsys.readouterr().out
    assert "base" in out
    assert "fullstack" in out


def test_show_active_profiles_none(tmp_path, capsys):
    ai_status.show_profiles(tmp_path)
    assert capsys.readouterr().out.strip() == ""


def test_show_active_profiles_empty_file(tmp_path, capsys):
    (tmp_path / ".active").write_text("")
    ai_status.show_profiles(tmp_path)
    assert "no profiles" in capsys.readouterr().out.lower()


def test_cli_no_flags_calls_both(capsys):
    with patch("ai_status.fetch_proxy_stats", return_value={}) as mock_stats:
        with patch("ai_status.show_models") as mock_models:
            with patch("ai_status.show_profiles") as mock_profiles:
                old = sys.argv
                sys.argv = ["ai-status"]
                try:
                    ai_status.main()
                finally:
                    sys.argv = old
    mock_profiles.assert_called_once()
    mock_models.assert_called_once()
    mock_stats.assert_called_once()


def test_cli_proxy_flag_skips_models(capsys):
    with patch("ai_status.fetch_proxy_stats", return_value={"requests": 1}):
        with patch("ai_status.show_models") as mock_models:
            old = sys.argv
            sys.argv = ["ai-status", "--proxy"]
            try:
                ai_status.main()
            finally:
                sys.argv = old
    mock_models.assert_not_called()
