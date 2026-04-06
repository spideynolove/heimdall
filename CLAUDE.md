# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate venv before running anything
source /home/hung/env/.venv/bin/activate

# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Run a single test file
pytest tests/test_commands.py

# Run a single test by name
pytest tests/test_commands.py::test_load_creates_symlinks

# Scaffold ~/.ai-profiles/ directory structure
python scripts/scaffold-profiles.py
```

## Architecture

This project implements a **profile + task-routing system** for multi-model AI orchestration. All AI providers are invoked through `ccs` (Claude Code Switch), which makes every provider run as Claude Code — meaning they all share the same `CLAUDE.md`, agents, commands, hooks, and MCP config. Only the underlying model differs.

### Two source files

**`src/ai_profile.py`** — profile loader (Phase 1, complete)
- Manages `~/.ai-profiles/` → `~/.claude/` symlink lifecycle
- `cmd_load`: symlinks `{profile}/__{filename}` into `~/.claude/{agents,commands,skills,hooks}/`, appends profile's `CLAUDE.md` to `~/.claude/CLAUDE.md`, deep-merges `settings.json`
- `cmd_unload`: removes symlinks by prefix, rebuilds `CLAUDE.md` and `settings.json` from remaining active profiles
- Active state persisted in `~/.ai-profiles/.active` (space-separated profile names)
- Symlinks are prefixed `{profile_name}__{filename}` to prevent collisions between profiles
- `merge_settings`: deep-merges two `settings.json` dicts — `mcpServers` is shallow-merged, `hooks` is recursively merged, lists are concatenated and deduplicated

**`src/ai_dispatch.py`** — tmux-based task dispatcher (Phase 2, in progress)
- `dispatch(task, profile, session)`: loads profile if given, ensures tmux session+window exists, runs `claude -p '{task}'` in the pane, polls for a `<<<DONE>>>` sentinel, returns captured output
- Each profile gets its own named tmux window within the `ai-do` session
- Environment variables: `AI_DISPATCH_SESSION` (default: `ai-do`), `AI_PROFILES_DIR`, `AI_CLAUDE_DIR`

### Profile directory layout

```
~/.ai-profiles/
  base/                  # always-on baseline (CLAUDE.md, settings.json, commands/, agents/)
  fullstack/             # per-project-type overlays
  ml/
  ...
  orchestrator/          # Phase 3+: models.yaml, routing.yaml, usage/, queue/, checkpoints/
  .active                # space-separated list of currently loaded profiles
```

### Build roadmap (from `ai-cli-orchestration.md`)

| Phase | Status | Description |
|---|---|---|
| 1 | Complete | Profile loader: `ai-profile load/unload/status/list` |
| 2 | In progress | `ai-dispatch run <task>` via tmux |
| 3 | Planned | `ai-do`: keyword extraction → model routing → CCS invocation |
| 4 | Planned | Checkpoint/resume + failover on quota hit |
| 5 | Planned | `ai-status` dashboard, `ai-do --split` |
| 6 | Planned | Update subagents task-runner to use CCS invocation |

### Testing approach

Tests use `tmp_path` fixtures that create isolated `claude_dir` and `profiles_dir` trees. No mocking of the filesystem — tests exercise real symlink creation/removal. `ai_dispatch` tests mock `subprocess.run` to avoid requiring a live tmux session.
