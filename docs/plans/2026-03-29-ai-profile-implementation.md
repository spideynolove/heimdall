# ai-profile Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `ai-profile` — a Python stdlib-only CLI that loads/unloads named profile sets into `~/.claude/` by symlinking files and merging CLAUDE.md + settings.json.

**Architecture:** Single self-contained Python script `src/ai_profile.py` (no package, no imports outside stdlib). Installed by copying to `~/.claude/bin/ai-profile`. Tests import from the file directly. Env vars `AI_CLAUDE_DIR` and `AI_PROFILES_DIR` override defaults for testing.

**Tech Stack:** Python 3.8+ (stdlib only), pytest for tests, `#!/usr/bin/env python3` shebang.

---

## Pre-flight

```bash
mkdir -p /home/hung/Public/temp-2
cd /home/hung/Public/temp-2
git init
git add docs/
git commit -m "chore: add design docs for ai-profile phase 1"
```

---

### Task 1: Project scaffold

**Files:**
- Create: `src/ai_profile.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_merge.py`
- Create: `tests/test_symlinks.py`
- Create: `tests/test_commands.py`
- Create: `pyproject.toml`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "ai-profile"
version = "0.1.0"
requires-python = ">=3.8"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

**Step 2: Create directory structure**

```bash
mkdir -p src tests
touch tests/__init__.py
```

**Step 3: Create conftest.py with shared fixtures**

```python
# tests/conftest.py
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
```

**Step 4: Create empty src/ai_profile.py and test files**

```python
# src/ai_profile.py
```

```python
# tests/test_merge.py
# tests/test_symlinks.py
# tests/test_commands.py
```

**Step 5: Install pytest and run**

```bash
source /home/hung/env/.venv/bin/activate
uv pip install pytest pytest-cov
pytest -v
```

Expected: `no tests ran`

**Step 6: Commit**

```bash
git add src/ tests/ pyproject.toml
git commit -m "chore: scaffold ai-profile project with pytest fixtures"
```

---

### Task 2: settings.json deep-merge with array deduplication

**Files:**
- Modify: `src/ai_profile.py`
- Modify: `tests/test_merge.py`

**Step 1: Write failing tests**

```python
# tests/test_merge.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import importlib.util, types

spec = importlib.util.spec_from_file_location("ai_profile", Path(__file__).parent.parent / "src" / "ai_profile.py")
mod = importlib.util.load_module_from_spec(spec) if hasattr(importlib.util, "load_module_from_spec") else types.ModuleType("ai_profile")

from ai_profile import merge_settings


def test_merge_empty_overlay():
    base = {"permissions": ["Bash(git:*)"], "hooks": {"PostToolUse": []}}
    result = merge_settings(base, {})
    assert result == base


def test_merge_array_concatenation():
    base = {"hooks": {"PostToolUse": [{"command": "a.sh"}]}}
    overlay = {"hooks": {"PostToolUse": [{"command": "b.sh"}]}}
    result = merge_settings(base, overlay)
    assert result["hooks"]["PostToolUse"] == [
        {"command": "a.sh"}, {"command": "b.sh"}
    ]


def test_merge_array_dedup_by_command():
    base = {"hooks": {"PostToolUse": [{"command": "a.sh"}]}}
    overlay = {"hooks": {"PostToolUse": [{"command": "a.sh"}, {"command": "b.sh"}]}}
    result = merge_settings(base, overlay)
    assert result["hooks"]["PostToolUse"] == [
        {"command": "a.sh"}, {"command": "b.sh"}
    ]


def test_merge_mcp_servers_dedup_by_key():
    base = {"mcpServers": {"sqlite": {"command": "sqlite-mcp"}}}
    overlay = {"mcpServers": {"sqlite": {"command": "sqlite-mcp-new"}, "pg": {"command": "pg-mcp"}}}
    result = merge_settings(base, overlay)
    assert set(result["mcpServers"].keys()) == {"sqlite", "pg"}


def test_merge_scalar_overlay_wins():
    base = {"effortLevel": "low"}
    overlay = {"effortLevel": "high"}
    result = merge_settings(base, overlay)
    assert result["effortLevel"] == "high"


def test_merge_permissions_dedup():
    base = {"permissions": ["Bash(git:*)", "Bash(npm:*)"]}
    overlay = {"permissions": ["Bash(npm:*)", "Bash(docker:*)"]}
    result = merge_settings(base, overlay)
    assert sorted(result["permissions"]) == sorted(["Bash(git:*)", "Bash(npm:*)", "Bash(docker:*)"])
```

**Step 2: Run to verify all fail**

```bash
pytest tests/test_merge.py -v
```

Expected: `ImportError` — `merge_settings` not defined yet

**Step 3: Implement in src/ai_profile.py**

```python
#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Settings merge
# ---------------------------------------------------------------------------

def _dedup_list(items: list, key_fn) -> list:
    seen: dict = {}
    for item in items:
        k = key_fn(item)
        if k not in seen:
            seen[k] = item
    return list(seen.values())


def merge_settings(base: dict, overlay: dict) -> dict:
    result: dict = {}
    for k in set(base) | set(overlay):
        if k not in overlay:
            result[k] = base[k]
        elif k not in base:
            result[k] = overlay[k]
        elif k == "mcpServers":
            result[k] = {**base[k], **overlay[k]}
        elif k == "hooks" and isinstance(base[k], dict) and isinstance(overlay[k], dict):
            result[k] = merge_settings(base[k], overlay[k])
        elif isinstance(base[k], list) and isinstance(overlay[k], list):
            combined = base[k] + overlay[k]
            if combined and isinstance(combined[0], dict) and "command" in combined[0]:
                result[k] = _dedup_list(combined, lambda x: x["command"])
            else:
                result[k] = _dedup_list(combined, lambda x: x)
        elif isinstance(base[k], dict) and isinstance(overlay[k], dict):
            result[k] = merge_settings(base[k], overlay[k])
        else:
            result[k] = overlay[k]
    return result
```

**Step 4: Run tests**

```bash
pytest tests/test_merge.py -v
```

Expected: 6 PASSED

**Step 5: Commit**

```bash
git add src/ai_profile.py tests/test_merge.py
git commit -m "feat: implement settings.json deep-merge with array deduplication"
```

---

### Task 3: CLAUDE.md merge (base never duplicated)

**Files:**
- Modify: `src/ai_profile.py`
- Modify: `tests/test_merge.py`

**Step 1: Write failing tests**

```python
# append to tests/test_merge.py
from ai_profile import build_claude_md


def test_build_claude_md_base_only(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "CLAUDE.md").write_text("# Base\n")
    assert build_claude_md(tmp_path, []) == "# Base\n"


def test_build_claude_md_with_profile(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "CLAUDE.md").write_text("# Base\n")
    (tmp_path / "fullstack").mkdir()
    (tmp_path / "fullstack" / "CLAUDE.md").write_text("# Fullstack\n")
    result = build_claude_md(tmp_path, ["fullstack"])
    assert "# Base\n" in result
    assert "# Profile: fullstack" in result
    assert "# Fullstack\n" in result


def test_build_claude_md_base_in_active_not_duplicated(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "CLAUDE.md").write_text("# Base\n")
    result = build_claude_md(tmp_path, ["base"])
    assert result.count("# Base") == 1


def test_build_claude_md_profile_without_claude_md(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "CLAUDE.md").write_text("# Base\n")
    (tmp_path / "vue").mkdir()
    result = build_claude_md(tmp_path, ["vue"])
    assert result == "# Base\n"


def test_build_claude_md_missing_base_warns(tmp_path, capsys):
    (tmp_path / "fullstack").mkdir()
    (tmp_path / "fullstack" / "CLAUDE.md").write_text("# Fullstack\n")
    result = build_claude_md(tmp_path, ["fullstack"])
    captured = capsys.readouterr()
    assert "warning" in (captured.out + captured.err).lower()
    assert "# Fullstack\n" in result
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_merge.py -k "claude_md" -v
```

Expected: all FAILED

**Step 3: Implement `build_claude_md`**

```python
# add to src/ai_profile.py

def build_claude_md(profiles_dir: Path, active: list[str]) -> str:
    base_path = profiles_dir / "base" / "CLAUDE.md"
    parts: list[str] = []
    if base_path.exists():
        parts.append(base_path.read_text())
    else:
        print("warning: base/CLAUDE.md not found", file=sys.stderr)
    for name in active:
        if name == "base":
            continue  # base already included above
        p = profiles_dir / name / "CLAUDE.md"
        if p.exists():
            parts.append(f"\n---\n# Profile: {name}\n")
            parts.append(p.read_text())
    return "".join(parts)
```

**Step 4: Run all merge tests**

```bash
pytest tests/test_merge.py -v
```

Expected: all PASSED

**Step 5: Commit**

```bash
git add src/ai_profile.py tests/test_merge.py
git commit -m "feat: implement CLAUDE.md merge, skip base duplication when base in active list"
```

---

### Task 4: Symlink load/unload (files and directories)

**Files:**
- Modify: `src/ai_profile.py`
- Modify: `tests/test_symlinks.py`

**Step 1: Write failing tests**

```python
# tests/test_symlinks.py
from ai_profile import symlink_profile, unsymlink_profile


def test_symlink_creates_prefixed_file_links(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    assert (claude_dir / "agents" / "fullstack__react-agent.md").is_symlink()
    assert (claude_dir / "commands" / "fullstack__e2e.md").is_symlink()


def test_symlink_creates_prefixed_dir_links_for_skills(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    link = claude_dir / "skills" / "fullstack__playwright"
    assert link.is_symlink()
    assert link.is_dir()


def test_symlink_points_to_correct_target(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    link = claude_dir / "agents" / "fullstack__react-agent.md"
    assert link.resolve() == (profile_a / "agents" / "react-agent.md").resolve()


def test_symlink_idempotent(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    symlink_profile("fullstack", profile_a, claude_dir)
    assert len(list((claude_dir / "agents").glob("fullstack__*"))) == 1


def test_unsymlink_removes_file_links(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    unsymlink_profile("fullstack", claude_dir)
    assert not (claude_dir / "agents" / "fullstack__react-agent.md").exists()


def test_unsymlink_removes_dir_links(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    unsymlink_profile("fullstack", claude_dir)
    assert not (claude_dir / "skills" / "fullstack__playwright").exists()


def test_unsymlink_skips_broken_links(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    (profile_a / "agents" / "react-agent.md").unlink()
    unsymlink_profile("fullstack", claude_dir)
    assert not list((claude_dir / "agents").glob("fullstack__*"))


def test_unsymlink_does_not_touch_other_profiles(claude_dir, profiles_dir):
    other = profiles_dir / "ml"
    (other / "agents").mkdir(parents=True)
    (other / "agents" / "python-reviewer.md").write_text("# ML\n")
    symlink_profile("ml", other, claude_dir)
    symlink_profile("fullstack", profiles_dir / "fullstack", claude_dir)
    unsymlink_profile("fullstack", claude_dir)
    assert (claude_dir / "agents" / "ml__python-reviewer.md").is_symlink()
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_symlinks.py -v
```

Expected: all FAILED

**Step 3: Implement `symlink_profile` and `unsymlink_profile`**

```python
# add to src/ai_profile.py

SUBDIRS = ("agents", "commands", "skills", "hooks")


def symlink_profile(name: str, profile_dir: Path, claude_dir: Path) -> None:
    for sub in SUBDIRS:
        src_dir = profile_dir / sub
        dst_dir = claude_dir / sub
        if not src_dir.is_dir():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src_entry in src_dir.iterdir():
            dst = dst_dir / f"{name}__{src_entry.name}"
            if dst.is_symlink():
                continue
            dst.symlink_to(src_entry)


def unsymlink_profile(name: str, claude_dir: Path) -> None:
    prefix = f"{name}__"
    for sub in SUBDIRS:
        sub_dir = claude_dir / sub
        if not sub_dir.is_dir():
            continue
        for link in sub_dir.iterdir():
            if link.name.startswith(prefix) and link.is_symlink():
                link.unlink()
```

Note: `src_entry` can be a file or directory — `symlink_to` works for both.

**Step 4: Run tests**

```bash
pytest tests/test_symlinks.py -v
```

Expected: all PASSED

**Step 5: Commit**

```bash
git add src/ai_profile.py tests/test_symlinks.py
git commit -m "feat: implement symlink_profile handling both files and directories (skills)"
```

---

### Task 5: .active file management

**Files:**
- Modify: `src/ai_profile.py`
- Modify: `tests/test_commands.py`

**Step 1: Write failing tests**

```python
# tests/test_commands.py
from ai_profile import get_active, set_active


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
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_commands.py -k "active" -v
```

Expected: all FAILED

**Step 3: Implement `get_active` and `set_active`**

```python
# add to src/ai_profile.py

def get_active(profiles_dir: Path) -> list[str]:
    active_file = profiles_dir / ".active"
    if not active_file.exists():
        return []
    return [p for p in active_file.read_text().strip().split() if p]


def set_active(profiles_dir: Path, profiles: list[str]) -> None:
    (profiles_dir / ".active").write_text(" ".join(profiles))
```

**Step 4: Run tests**

```bash
pytest tests/test_commands.py -v
```

Expected: all PASSED

**Step 5: Commit**

```bash
git add src/ai_profile.py tests/test_commands.py
git commit -m "feat: implement .active file management"
```

---

### Task 6: `load` and `unload` commands (integration)

**Files:**
- Modify: `src/ai_profile.py`
- Modify: `tests/test_commands.py`

**Step 1: Write failing tests**

```python
# append to tests/test_commands.py
import json
import pytest
from ai_profile import cmd_load, cmd_unload


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
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_commands.py -k "load or unload" -v
```

Expected: all FAILED

**Step 3: Implement `cmd_load` and `cmd_unload`**

```python
# add to src/ai_profile.py

def _read_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"error: failed to parse {path}: {e}", file=sys.stderr)
        sys.exit(1)


def _build_settings(profiles_dir: Path, active: list[str]) -> dict:
    result = _read_settings(profiles_dir / "base" / "settings.json")
    for name in active:
        if name == "base":
            continue  # base already applied above
        overlay = _read_settings(profiles_dir / name / "settings.json")
        result = merge_settings(result, overlay)
    return result


def cmd_load(name: str, profiles_dir: Path, claude_dir: Path) -> None:
    profile_dir = profiles_dir / name
    if not profile_dir.is_dir():
        print(f"error: profile '{name}' not found in {profiles_dir}", file=sys.stderr)
        sys.exit(1)
    active = get_active(profiles_dir)
    if name in active:
        print(f"profile '{name}' is already active — skipping")
        return
    symlink_profile(name, profile_dir, claude_dir)
    active.append(name)
    set_active(profiles_dir, active)
    (claude_dir / "CLAUDE.md").write_text(build_claude_md(profiles_dir, active))
    (claude_dir / "settings.json").write_text(
        json.dumps(_build_settings(profiles_dir, active), indent=2)
    )
    print(f"loaded profile '{name}'")


def cmd_unload(name: str, profiles_dir: Path, claude_dir: Path) -> None:
    active = get_active(profiles_dir)
    if name not in active:
        print(f"profile '{name}' is not active")
        return
    unsymlink_profile(name, claude_dir)
    active.remove(name)
    set_active(profiles_dir, active)
    (claude_dir / "CLAUDE.md").write_text(build_claude_md(profiles_dir, active))
    (claude_dir / "settings.json").write_text(
        json.dumps(_build_settings(profiles_dir, active), indent=2)
    )
    print(f"unloaded profile '{name}'")
```

**Step 4: Run tests**

```bash
pytest tests/test_commands.py -v
```

Expected: all PASSED

**Step 5: Commit**

```bash
git add src/ai_profile.py tests/test_commands.py
git commit -m "feat: implement cmd_load and cmd_unload with full integration"
```

---

### Task 7: `status` and `list` commands

**Files:**
- Modify: `src/ai_profile.py`
- Modify: `tests/test_commands.py`

**Step 1: Write failing tests**

```python
# append to tests/test_commands.py
from ai_profile import cmd_status, cmd_list


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


def test_list_shows_profiles(profiles_dir, capsys):
    cmd_list(profiles_dir)
    assert "fullstack" in capsys.readouterr().out


def test_list_excludes_orchestrator(profiles_dir, capsys):
    (profiles_dir / "orchestrator").mkdir(exist_ok=True)
    cmd_list(profiles_dir)
    assert "orchestrator" not in capsys.readouterr().out


def test_list_marks_active(claude_dir, profiles_dir, profile_a, capsys):
    cmd_load("fullstack", profiles_dir, claude_dir)
    cmd_list(profiles_dir)
    out = capsys.readouterr().out
    fullstack_line = next(l for l in out.splitlines() if "fullstack" in l)
    assert "*" in fullstack_line or "active" in fullstack_line.lower()
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_commands.py -k "status or list" -v
```

Expected: all FAILED

**Step 3: Implement `cmd_status` and `cmd_list`**

```python
# add to src/ai_profile.py

_NON_PROFILE_DIRS = {"orchestrator"}


def cmd_status(profiles_dir: Path, claude_dir: Path) -> None:
    active = get_active(profiles_dir)
    if not active:
        print("no profiles active")
        return
    for name in active:
        print(f"\n[{name}]")
        for sub in SUBDIRS:
            sub_dir = claude_dir / sub
            if not sub_dir.is_dir():
                continue
            items = sorted(
                link.name.replace(f"{name}__", "")
                for link in sub_dir.iterdir()
                if link.name.startswith(f"{name}__") and link.is_symlink()
            )
            if items:
                print(f"  {sub}/: {', '.join(items)}")


def cmd_list(profiles_dir: Path) -> None:
    active = get_active(profiles_dir)
    profiles = sorted(
        p.name
        for p in profiles_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in _NON_PROFILE_DIRS
    )
    for name in profiles:
        marker = " *" if name in active else ""
        print(f"  {name}{marker}")
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASSED

**Step 5: Commit**

```bash
git add src/ai_profile.py tests/test_commands.py
git commit -m "feat: implement cmd_status and cmd_list, exclude orchestrator from list"
```

---

### Task 8: CLI entry point

**Files:**
- Modify: `src/ai_profile.py`
- Modify: `tests/test_commands.py`

**Step 1: Write failing test**

```python
# append to tests/test_commands.py
import os
import subprocess


def test_cli_load_runs(claude_dir, profiles_dir, profile_a):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "src" / "ai_profile.py"),
         "load", "fullstack"],
        env={**os.environ,
             "AI_CLAUDE_DIR": str(claude_dir),
             "AI_PROFILES_DIR": str(profiles_dir)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "loaded" in result.stdout


def test_cli_unknown_command_exits(claude_dir, profiles_dir):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "src" / "ai_profile.py"),
         "badcmd"],
        env={**os.environ,
             "AI_CLAUDE_DIR": str(claude_dir),
             "AI_PROFILES_DIR": str(profiles_dir)},
        capture_output=True, text=True,
    )
    assert result.returncode != 0
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_commands.py -k "cli" -v
```

Expected: FAILED — no `if __name__ == "__main__"` block yet

**Step 3: Add CLI main block to src/ai_profile.py**

```python
# add at the bottom of src/ai_profile.py

def main() -> None:
    claude_dir = Path(os.environ.get("AI_CLAUDE_DIR", Path.home() / ".claude"))
    profiles_dir = Path(os.environ.get("AI_PROFILES_DIR", Path.home() / ".ai-profiles"))

    args = sys.argv[1:]
    if not args:
        print("usage: ai-profile <load|unload|status|list> [name]", file=sys.stderr)
        sys.exit(1)

    cmd = args[0]
    if cmd == "load":
        if len(args) < 2:
            print("error: load requires a profile name", file=sys.stderr)
            sys.exit(1)
        cmd_load(args[1], profiles_dir, claude_dir)
    elif cmd == "unload":
        if len(args) < 2:
            print("error: unload requires a profile name", file=sys.stderr)
            sys.exit(1)
        cmd_unload(args[1], profiles_dir, claude_dir)
    elif cmd == "status":
        cmd_status(profiles_dir, claude_dir)
    elif cmd == "list":
        cmd_list(profiles_dir)
    else:
        print(f"error: unknown command '{cmd}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASSED

**Step 5: Commit**

```bash
git add src/ai_profile.py tests/test_commands.py
git commit -m "feat: add CLI main block with AI_CLAUDE_DIR/AI_PROFILES_DIR env overrides"
```

---

### Task 9: Install to `~/.claude/bin/` + symlink to `~/.local/bin/`

**Files:**
- Create: `~/.claude/bin/ai-profile`

**Step 1: Create bin dir and copy script**

```bash
mkdir -p ~/.claude/bin
cp /home/hung/Public/temp-2/src/ai_profile.py ~/.claude/bin/ai-profile
chmod +x ~/.claude/bin/ai-profile
```

The script is self-contained — no package imports, no sys.path manipulation needed.

**Step 2: Symlink into `~/.local/bin/`**

```bash
ln -sf ~/.claude/bin/ai-profile ~/.local/bin/ai-profile
```

**Step 3: Verify**

```bash
which ai-profile
ai-profile list
```

Expected:
```
/home/hung/.local/bin/ai-profile
  (empty — ~/.ai-profiles/ not created yet)
```

**Step 4: Commit**

```bash
cd /home/hung/Public/temp-2
git add src/ai_profile.py
git commit -m "chore: finalize ai-profile single-file script for install"
```

---

### Task 10: Create `~/.ai-profiles/` skeleton

**Files:**
- Create: `scripts/scaffold-profiles.py`
- Create: `~/.ai-profiles/` full directory tree

**Step 1: Create scaffold script**

```python
#!/usr/bin/env python3
# scripts/scaffold-profiles.py
from pathlib import Path

PROFILES_DIR = Path.home() / ".ai-profiles"

PROFILE_SUBDIRS = {
    "base":         ["agents", "commands", "skills", "hooks"],
    "fullstack":    ["agents", "commands", "skills", "hooks"],
    "vue":          ["skills"],
    "ml":           ["agents"],
    "backend-go":   ["agents"],
    "backend-rust": ["agents"],
    "trading":      ["agents", "skills"],
    "devops":       ["commands", "hooks"],
    "automation":   ["agents", "commands", "hooks"],
    "refactor":     ["agents"],
}

for profile, subdirs in PROFILE_SUBDIRS.items():
    for sub in subdirs:
        (PROFILES_DIR / profile / sub).mkdir(parents=True, exist_ok=True)
    claude_md = PROFILES_DIR / profile / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text(f"# Profile: {profile}\n")
    settings = PROFILES_DIR / profile / "settings.json"
    if not settings.exists():
        settings.write_text("{}")

active = PROFILES_DIR / ".active"
if not active.exists():
    active.write_text("")

orc = PROFILES_DIR / "orchestrator"
for d in ("usage", "queue", "checkpoints"):
    (orc / d).mkdir(parents=True, exist_ok=True)

models_yaml = orc / "models.yaml"
if not models_yaml.exists():
    models_yaml.write_text("# Phase 3 placeholder\n# models:\n")

routing_yaml = orc / "routing.yaml"
if not routing_yaml.exists():
    routing_yaml.write_text("# Phase 3 placeholder\n# rules:\n")

print("~/.ai-profiles/ scaffold complete")
```

**Step 2: Run it**

```bash
mkdir -p /home/hung/Public/temp-2/scripts
# write the file above to scripts/scaffold-profiles.py
python3 /home/hung/Public/temp-2/scripts/scaffold-profiles.py
```

Expected: `~/.ai-profiles/ scaffold complete`

**Step 3: Verify with ai-profile list**

```bash
ai-profile list
```

Expected:
```
  automation
  backend-go
  backend-rust
  base
  devops
  fullstack
  ml
  refactor
  trading
  vue
```

(No `orchestrator` in the list)

**Step 4: Commit**

```bash
cd /home/hung/Public/temp-2
git add scripts/scaffold-profiles.py
git commit -m "chore: add scaffold script for ~/.ai-profiles/ directory structure"
```

---

### Task 11: Smoke test the full flow

**Step 1: Load base**

```bash
ai-profile load base
```

Expected: `loaded profile 'base'`

**Step 2: Load fullstack**

```bash
ai-profile load fullstack
```

Expected: `loaded profile 'fullstack'`

**Step 3: Check status**

```bash
ai-profile status
```

Expected: shows `[base]` and `[fullstack]` with their file contributions

**Step 4: Verify .active**

```bash
cat ~/.ai-profiles/.active
```

Expected: `base fullstack`

**Step 5: Test idempotent guard**

```bash
ai-profile load base
```

Expected: `profile 'base' is already active — skipping`

**Step 6: Unload fullstack**

```bash
ai-profile unload fullstack
```

Expected: `unloaded profile 'fullstack'`

**Step 7: Verify CLAUDE.md no longer has fullstack section**

```bash
grep "Profile: fullstack" ~/.claude/CLAUDE.md && echo "FAIL" || echo "PASS"
```

Expected: `PASS`

**Step 8: Coverage check**

```bash
cd /home/hung/Public/temp-2
pytest tests/ --cov=ai_profile --cov-report=term-missing
```

Expected: ≥80% coverage

**Step 9: Final commit**

```bash
git add .
git commit -m "feat: ai-profile phase 1 complete — profile loader with load/unload/status/list"
```

---

## Reinstall after edits

When modifying `src/ai_profile.py` during development, sync to the installed location:

```bash
cp /home/hung/Public/temp-2/src/ai_profile.py ~/.claude/bin/ai-profile
```
