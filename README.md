# heimdall

Multi-model AI orchestration via [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) + Claude Code.

Every provider runs as Claude Code — same `CLAUDE.md`, agents, commands, hooks, and MCP config across all models. Only the underlying model differs.

---

## How it works

```
ai-do "implement JWT auth"
  → keyword match: implement → codex
  → ANTHROPIC_BASE_URL=http://localhost:8317 claude --model gpt-4o -p "..."
  → CLIProxyAPI routes to whichever Codex account has quota
```

CLIProxyAPI runs locally and handles all multi-account round-robin, quota failover, and OAuth. `ai-do` only decides *which model family* to use.

---

## Components

### `ai-profile` — profile loader (Phase 1)

Symlinks named profile sets into `~/.claude/` so every provider gets the right agents, commands, hooks, and MCP servers for the current project type.

```bash
ai-profile load fullstack    # symlink fullstack agents/commands/hooks into ~/.claude/
ai-profile unload fullstack  # remove them
ai-profile status            # show active profiles and their contributions
ai-profile list              # list available profiles (* = active)
```

Profiles live in `~/.ai-profiles/{name}/` with subdirs `agents/`, `commands/`, `skills/`, `hooks/`, plus `CLAUDE.md` and `settings.json`. Loading deep-merges settings and concatenates CLAUDE.md files.

### `ai-dispatch` — tmux dispatcher (Phase 2)

Runs tasks in named tmux panes, one pane per model/profile. Polls for a `<<<DONE>>>` sentinel.

```bash
ai-dispatch run "what is 2+2"
ai-dispatch run "implement auth" --profile fullstack --session ai-do
```

### `ai-do` — keyword router (Phase 3)

Reads `~/.ai-profiles/orchestrator/models.yaml` and `routing.yaml`, matches task keywords to the best model, then dispatches via CLIProxyAPI.

```bash
ai-do run "implement JWT auth"              # auto-route → codex
ai-do run "review the PR diff"             # auto-route → claude
ai-do run "analyze entire src/" --dry-run  # preview routing without running
ai-do run "design the schema" --model deepseek  # force a specific model
```

---

## CLIProxyAPI integration

All non-native models go through a local CLIProxyAPI instance (default: `http://localhost:8317`).

```yaml
# ~/.ai-profiles/orchestrator/models.yaml
models:
  claude:
    model: claude-sonnet-4-6
    proxy: ""                        # empty = direct to Anthropic
    strengths: [reasoning, review, debugging]
    failover: backup
  codex:
    model: gpt-4o
    proxy: http://localhost:8317     # through CLIProxyAPI
    strengths: [code_gen, scaffolding]
  gemini:
    model: gemini-2.5-pro
    proxy: http://localhost:8317
    strengths: [large_context, web_research]
```

Multi-account round-robin and quota failover are handled entirely by CLIProxyAPI — configure all your accounts there once and `ai-do` never needs to know about them.

---

## Routing rules

```yaml
# ~/.ai-profiles/orchestrator/routing.yaml
rules:
  - match: [architecture, planning, design, system, schema]
    primary: deepseek
    fallback: claude
  - match: [implement, generate, scaffold, boilerplate, crud, feature]
    primary: codex
    fallback: claude
  - match: [analyze, scan, codebase, large_context, all_files]
    primary: gemini
    fallback: km
  - match: [review, debug, fix, security, test]
    primary: claude
    fallback: backup
  - match: [docs, readme, translate, comment, multilingual]
    primary: glm
    fallback: openrouter
```

First keyword match wins. Unknown tasks default to `claude`.

---

## Setup

### 1. Start CLIProxyAPI

```bash
# Download and run — see https://github.com/router-for-me/CLIProxyAPI
./cliproxyapi --port 8317
```

Authenticate each provider once via its OAuth flow inside CLIProxyAPI. Multiple accounts per provider are listed in its `config.yaml` and load-balanced automatically.

### 2. Scaffold profiles directory

```bash
source /home/hung/env/.venv/bin/activate
python scripts/scaffold-profiles.py
```

This creates `~/.ai-profiles/` with profile directories and writes `orchestrator/models.yaml` + `routing.yaml` with the full model registry.

### 3. Install entry points

```bash
pip install -e ".[dev]"
```

Registers `ai-profile`, `ai-dispatch`, and `ai-do` as CLI commands.

---

## Development

```bash
source /home/hung/env/.venv/bin/activate

pytest                                    # run all tests
pytest --cov=src --cov-report=term-missing  # with coverage (target ≥ 80%)
pytest tests/test_ai_do.py -v             # single file
```

Tests use `tmp_path` fixtures with real symlink I/O. `ai_dispatch` tests mock `subprocess.run` to avoid requiring a live tmux session.

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| 1 | Complete | `ai-profile load/unload/status/list` |
| 2 | Complete | `ai-dispatch run` via tmux panes |
| 3 | Complete | `ai-do run` keyword router + CLIProxyAPI dispatch |
| 4 | Planned | Cross-model fallback chain on quota hit |
| 5 | Planned | `ai-do --split` parallel subtasks, `ai-status` dashboard |
| 6 | Planned | Update subagent task-runner to use CLIProxyAPI invocation |

---

## Reference

- [Original design doc](docs/reference/ai-cli-orchestration.md)
- [Phase 3 implementation plan](docs/plans/2026-04-06-ai-do-phase3.md)
- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
