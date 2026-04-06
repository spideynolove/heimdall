# Phase 1 Closeout — Safe Smoke Test Procedure

## Preconditions

### 1. Fix the broken-symlink gap in `src/ai_profile.py`

`symlink_profile` currently skips any existing symlink, including broken ones, which can silently block re-creation.

**Before**

```python
if dst.is_symlink():
    continue
```

**After**

```python
if dst.is_symlink() and dst.exists():
    continue
if dst.is_symlink():
    dst.unlink()
```

Add a regression test in `tests/test_symlinks.py`:

```python
def test_symlink_recreates_after_broken_destination(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    link = claude_dir / "agents" / "fullstack__react-agent.md"
    link.unlink()
    link.symlink_to("/nonexistent/path")
    symlink_profile("fullstack", profile_a, claude_dir)
    assert link.exists() and link.is_symlink()
```

### 2. Set up a project-local venv and install `pytest-cov`

```bash
cd /path/to/temp-2
uv venv
source .venv/bin/activate
uv pip install pytest-cov
```

Replace `/path/to/temp-2` with the actual project location. All later steps assume you are in the project root with the venv active.

---

## Risk model

| Option | Risk |
|---|---|
| Real `~/.claude` | High — contaminates a live environment and existing files can hide bugs |
| Another live project's `.claude` | High — same contamination risk, same hidden-bug risk |
| Disposable sandbox | Low — isolated and reproducible |

Use a disposable sandbox. The current code already supports that:

- `AI_CLAUDE_DIR` overrides `~/.claude`
- `AI_PROFILES_DIR` overrides `~/.ai-profiles`
- `scripts/scaffold-profiles.py` writes through `Path.home()`, so `HOME` can isolate it

---

## Smoke test procedure

All steps assume you are in the project root with the venv active:

```bash
cd /path/to/temp-2
source .venv/bin/activate
```

### 1. Create sandbox

```bash
export SMOKE=/tmp/ai-profile-smoke
mkdir -p "$SMOKE"
```

### 2. Run scaffold into sandbox

```bash
HOME="$SMOKE" python3 scripts/scaffold-profiles.py
```

Expected output:

```text
~/.ai-profiles/ scaffold complete
```

Note: the message is cosmetic. The script writes to `$SMOKE/.ai-profiles/`, not your real home directory.

Verify the tree:

```bash
ls "$SMOKE/.ai-profiles/"
ls "$SMOKE/.ai-profiles/orchestrator/"
```

Expected under `$SMOKE/.ai-profiles/`:

- profile directories: `base/`, `fullstack/`, `ml/`, etc.
- `.active`

Expected under `$SMOKE/.ai-profiles/orchestrator/`:

- `usage/`
- `queue/`
- `checkpoints/`
- `models.yaml`
- `routing.yaml`

### 3. Seed stub content into the `fullstack` profile

The scaffold creates empty subdirectories. `symlink_profile` has nothing to link unless the profile contains at least one file.

```bash
echo "# stub" > "$SMOKE/.ai-profiles/fullstack/agents/stub-agent.md"
```

### 4. Smoke test CLI commands

```bash
export AI_CLAUDE_DIR="$SMOKE/.claude"
export AI_PROFILES_DIR="$SMOKE/.ai-profiles"

mkdir -p "$SMOKE/.claude"/{agents,commands,skills,hooks}
touch "$SMOKE/.claude/CLAUDE.md"
printf '{}' > "$SMOKE/.claude/settings.json"

python src/ai_profile.py load fullstack
ls "$SMOKE/.claude/agents/"
cat "$SMOKE/.claude/CLAUDE.md"
python -m json.tool "$SMOKE/.claude/settings.json"
python src/ai_profile.py status
python src/ai_profile.py list
python src/ai_profile.py unload fullstack
ls "$SMOKE/.claude/agents/"
```

Expected:

- `load` prints `loaded profile 'fullstack'`
- `agents/` shows `fullstack__stub-agent.md`
- `CLAUDE.md` contains `# Profile: fullstack`
- `json.tool` prints valid JSON without error
- `status` shows a `[fullstack]` block listing `stub-agent.md`
- `list` marks `fullstack` active
- `unload` prints `unloaded profile 'fullstack'`
- final `ls` shows no `fullstack__*` links

### 5. Run tests with coverage

```bash
python -m pytest --cov=src --cov-report=term-missing -q
```

Expected: full suite passes, coverage `>= 80%`.

If coverage is below `80%`, use the `term-missing` output to identify uncovered branches and add tests before proceeding to Step 6.

### 6. Install only after sandbox passes

Add `~/.local/bin` to `PATH` if not already present (requires bash):

```bash
[[ ":$PATH:" == *":$HOME/.local/bin:"* ]] || export PATH="$HOME/.local/bin:$PATH"
```

Then install:

```bash
mkdir -p ~/.claude/bin ~/.local/bin
cp src/ai_profile.py ~/.claude/bin/ai-profile
chmod +x ~/.claude/bin/ai-profile
ln -sf ~/.claude/bin/ai-profile ~/.local/bin/ai-profile
which ai-profile
ai-profile list
```

### 7. Cleanup

```bash
rm -rf "$SMOKE"
unset SMOKE AI_CLAUDE_DIR AI_PROFILES_DIR
deactivate
```

---

## Pass criteria

### Automated

| Check | Pass condition |
|---|---|
| Broken symlink fix | `test_symlink_recreates_after_broken_destination` passes |
| Full suite | All tests pass |
| Coverage | `>= 80%` |

### Manual smoke test

| Check | Pass condition |
|---|---|
| Scaffold | `$SMOKE/.ai-profiles/` tree created with all profiles and `orchestrator/` subdirs |
| `orchestrator/` contents | `usage/`, `queue/`, `checkpoints/`, `models.yaml`, `routing.yaml` present |
| Load | `fullstack__stub-agent.md` symlink appears under `$SMOKE/.claude/agents/` |
| CLAUDE.md | Contains `# Profile: fullstack` after load |
| settings.json | `python -m json.tool` exits without error |
| Unload | No `fullstack__*` links remain under `$SMOKE/.claude/` |
| Install | `which ai-profile` resolves to `~/.local/bin/ai-profile` |
| PATH check | `ai-profile list` runs successfully |

---

## Changelog

### Portability fix — project-local venv

Replaced all references to a machine-specific global venv with a project-local `.venv`:

1. **Precondition 2**: `uv venv && source .venv/bin/activate && uv pip install pytest-cov` — creates the venv inside the project
2. **All steps**: consolidated `cd /path/to/temp-2 && source .venv/bin/activate` at the top; all `python` calls use relative paths (`src/ai_profile.py`, `scripts/scaffold-profiles.py`)
3. **`python3`**: scaffold step uses `python3` explicitly to avoid Python 2 ambiguity
4. **`.gitignore`**: added `.venv/` so the venv is not committed
5. **Cleanup**: added `deactivate` to Step 7 so the shell is fully restored after the test run

On any other machine: `uv venv && uv pip install pytest-cov` is enough to reproduce the environment.
