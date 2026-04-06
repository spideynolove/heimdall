import pytest
from pathlib import Path


@pytest.fixture
def claude_dir(tmp_path):
    d = tmp_path / "claude"
    for sub in ("agents", "commands", "skills", "hooks"):
        (d / sub).mkdir(parents=True)
    (d / "CLAUDE.md").write_text("# Base\n")
    (d / "settings.json").write_text("{}")
    return d


@pytest.fixture
def profiles_dir(tmp_path):
    d = tmp_path / "profiles"
    base = d / "base"
    for sub in ("agents", "commands", "skills", "hooks"):
        (base / sub).mkdir(parents=True)
    (base / "CLAUDE.md").write_text("# Base profile\n")
    (base / "settings.json").write_text(
        '{"hooks": {"PostToolUse": []}, "permissions": []}'
    )
    (d / ".active").write_text("")
    return d


@pytest.fixture
def profile_a(profiles_dir):
    p = profiles_dir / "fullstack"
    for sub in ("agents", "commands", "skills", "hooks"):
        (p / sub).mkdir(parents=True)
    (p / "agents" / "react-agent.md").write_text("# React Agent\n")
    (p / "commands" / "e2e.md").write_text("# E2E command\n")
    skill_dir = p / "skills" / "playwright"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Playwright skill\n")
    (p / "CLAUDE.md").write_text("# Fullstack additions\n")
    (p / "settings.json").write_text(
        '{"hooks": {"PostToolUse": [{"command": "hook-a.sh"}]}, "permissions": ["Bash(npm:*)"]}'
    )
    return p
