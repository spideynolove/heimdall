import json
import os
import subprocess
import sys
import pytest
from pathlib import Path
from ai_profile import get_active, set_active, cmd_load, cmd_unload, cmd_status, cmd_list


def test_get_active_empty(profiles_dir):
    (profiles_dir / ".active").write_text("")
    assert get_active(profiles_dir) == []


def test_get_active_single(profiles_dir):
    (profiles_dir / ".active").write_text("fullstack")
    assert get_active(profiles_dir) == ["fullstack"]


def test_get_active_multiple(profiles_dir):
    (profiles_dir / ".active").write_text("base fullstack vue")
    assert get_active(profiles_dir) == ["base", "fullstack", "vue"]


def test_set_active_writes(profiles_dir):
    set_active(profiles_dir, ["fullstack", "vue"])
    assert (profiles_dir / ".active").read_text() == "fullstack vue"


def test_set_active_empty(profiles_dir):
    set_active(profiles_dir, [])
    assert (profiles_dir / ".active").read_text() == ""


def test_load_adds_to_active(claude_dir, profiles_dir, profile_a):
    cmd_load("fullstack", profiles_dir, claude_dir)
    assert "fullstack" in get_active(profiles_dir)


def test_load_creates_symlinks(claude_dir, profiles_dir, profile_a):
    cmd_load("fullstack", profiles_dir, claude_dir)
    assert (claude_dir / "agents" / "fullstack__react-agent.md").is_symlink()


def test_load_creates_skill_dir_symlinks(claude_dir, profiles_dir, profile_a):
    cmd_load("fullstack", profiles_dir, claude_dir)
    assert (claude_dir / "skills" / "fullstack__playwright").is_symlink()


def test_load_writes_claude_md(claude_dir, profiles_dir, profile_a):
    cmd_load("fullstack", profiles_dir, claude_dir)
    content = (claude_dir / "CLAUDE.md").read_text()
    assert "# Profile: fullstack" in content


def test_load_writes_settings(claude_dir, profiles_dir, profile_a):
    cmd_load("fullstack", profiles_dir, claude_dir)
    s = json.loads((claude_dir / "settings.json").read_text())
    assert "Bash(npm:*)" in s.get("permissions", [])


def test_load_idempotent(claude_dir, profiles_dir, profile_a, capsys):
    cmd_load("fullstack", profiles_dir, claude_dir)
    cmd_load("fullstack", profiles_dir, claude_dir)
    captured = capsys.readouterr()
    assert "already" in captured.out.lower()
    assert get_active(profiles_dir).count("fullstack") == 1


def test_load_unknown_profile_exits(claude_dir, profiles_dir):
    with pytest.raises(SystemExit):
        cmd_load("nonexistent", profiles_dir, claude_dir)


def test_unload_removes_from_active(claude_dir, profiles_dir, profile_a):
    cmd_load("fullstack", profiles_dir, claude_dir)
    cmd_unload("fullstack", profiles_dir, claude_dir)
    assert "fullstack" not in get_active(profiles_dir)


def test_unload_removes_symlinks(claude_dir, profiles_dir, profile_a):
    cmd_load("fullstack", profiles_dir, claude_dir)
    cmd_unload("fullstack", profiles_dir, claude_dir)
    assert not list((claude_dir / "agents").glob("fullstack__*"))


def test_unload_rewrites_claude_md(claude_dir, profiles_dir, profile_a):
    cmd_load("fullstack", profiles_dir, claude_dir)
    cmd_unload("fullstack", profiles_dir, claude_dir)
    assert "# Profile: fullstack" not in (claude_dir / "CLAUDE.md").read_text()


def test_unload_inactive_warns(claude_dir, profiles_dir, capsys):
    cmd_unload("fullstack", profiles_dir, claude_dir)
    captured = capsys.readouterr()
    assert "not active" in (captured.out + captured.err).lower()


def test_unload_does_not_touch_other_profile_symlinks(claude_dir, profiles_dir, profile_a):
    ml = profiles_dir / "ml"
    (ml / "agents").mkdir(parents=True)
    (ml / "agents" / "python-reviewer.md").write_text("# ML\n")
    cmd_load("ml", profiles_dir, claude_dir)
    cmd_load("fullstack", profiles_dir, claude_dir)
    cmd_unload("fullstack", profiles_dir, claude_dir)
    assert (claude_dir / "agents" / "ml__python-reviewer.md").is_symlink()


def test_status_shows_active_profile(claude_dir, profiles_dir, profile_a, capsys):
    cmd_load("fullstack", profiles_dir, claude_dir)
    cmd_status(profiles_dir, claude_dir)
    assert "fullstack" in capsys.readouterr().out


def test_status_shows_contributions(claude_dir, profiles_dir, profile_a, capsys):
    cmd_load("fullstack", profiles_dir, claude_dir)
    cmd_status(profiles_dir, claude_dir)
    out = capsys.readouterr().out
    assert "react-agent.md" in out or "agents" in out


def test_status_empty(profiles_dir, claude_dir, capsys):
    cmd_status(profiles_dir, claude_dir)
    out = capsys.readouterr().out
    assert "no profiles" in out.lower() or out.strip() == ""


def test_list_shows_profiles(profiles_dir, profile_a, capsys):
    cmd_list(profiles_dir)
    assert "fullstack" in capsys.readouterr().out


def test_list_excludes_orchestrator(profiles_dir, capsys):
    (profiles_dir / "orchestrator").mkdir(exist_ok=True)
    cmd_list(profiles_dir)
    assert "orchestrator" not in capsys.readouterr().out


def test_list_marks_active(claude_dir, profiles_dir, profile_a, capsys):
    cmd_load("fullstack", profiles_dir, claude_dir)
    capsys.readouterr()  # drain load output
    cmd_list(profiles_dir)
    out = capsys.readouterr().out
    fullstack_line = next(l for l in out.splitlines() if "fullstack" in l)
    assert "*" in fullstack_line or "active" in fullstack_line.lower()


_SCRIPT = str(Path(__file__).parent.parent / "src" / "ai_profile.py")


def test_cli_load_runs(claude_dir, profiles_dir, profile_a):
    result = subprocess.run(
        [sys.executable, _SCRIPT, "load", "fullstack"],
        env={**os.environ,
             "AI_CLAUDE_DIR": str(claude_dir),
             "AI_PROFILES_DIR": str(profiles_dir)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "loaded" in result.stdout


def test_cli_unknown_command_exits(claude_dir, profiles_dir):
    result = subprocess.run(
        [sys.executable, _SCRIPT, "badcmd"],
        env={**os.environ,
             "AI_CLAUDE_DIR": str(claude_dir),
             "AI_PROFILES_DIR": str(profiles_dir)},
        capture_output=True, text=True,
    )
    assert result.returncode != 0
