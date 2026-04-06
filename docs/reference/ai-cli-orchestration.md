# Multi-Model AI Orchestration via CCS + Claude Code

A profile + task-routing system powered by `ccs` (Claude Code Switch), where every provider runs through Claude Code's full feature set.

---

## Problem

- Claude Code hits the 5-hour subscription limit; switching accounts requires re-login
- Other AI models have different strengths and cost structures
- No standard way to load different toolsets per project type, route tasks to the right model, or fall back automatically when a limit is hit

**Goal:** One command assigns a task to the best available model, loads the right config set, falls back when limits are hit — all without re-login and without losing Claude Code's full feature set.

---

## Key Insight: CCS Makes Everything Claude Code

`ccs` (Claude Code Switch) routes all providers through Claude Code's Anthropic-compatible client. Every `ccs <provider>` launch is Claude Code running with a different model backend. The consequence:

- Every provider gets your full `CLAUDE.md`, agents, commands, hooks, MCP, skills
- No need to compare what gemini/qwen/codex natively support — irrelevant
- Continuity via `.aim/`, shared workspace, identical system prompt across all models
- Task-runner inconsistency disappears — same Claude Code behavior, different model

The only variable between providers is **which model runs underneath**.

---

## Part 1 — Your Provider Inventory

All launched via `ccs <name>`, all running as Claude Code:

| CCS command | Model / Backend | Auth | Best for |
|---|---|---|---|
| `ccs` | Claude Sonnet/Opus (account 1) | Subscription | Architecture, reasoning, complex debugging |
| `ccs backup` | Claude Sonnet/Opus (account 2) | Subscription | Auto-failover when account 1 hits 5h limit |
| `ccs gemini` | Gemini 2.5 Pro | OAuth (zero-config) | Large context, web-grounded research |
| `ccs codex` | GPT-4o / o-series | OAuth (zero-config) | Code generation, boilerplate |
| `ccs deepseek` | DeepSeek R1 / V3 | API key | Reasoning chains, planning |
| `ccs glm` | GLM-4 | API key | Cost-optimized repetitive tasks |
| `ccs km` | Kimi | API key | Long-context tasks (1M tokens) |
| `ccs mm` | Minimax M2 | API key | 1M context, cost-effective |
| `ccs openrouter` | 300+ models | API key ($25 budget) | Flexible routing, Minimax, others |
| `ccs qwen` | Qwen | OAuth (zero-config) | Code tasks, multilingual |
| `ccs kimi` | Kimi | OAuth | Long-context via OAuth |

**OAuth providers** (gemini, codex, qwen, kimi) require zero API key setup — authenticate once via device flow, CCS caches the token. CLIProxy daemon handles the translation.

**Two Claude accounts**: CCS isolates each via a separate `CLAUDE_CONFIG_DIR`. When account 1 hits the 5h limit, `ccs backup` picks up instantly with no re-login.

---

## Part 2 — Profile System

### Concept

Since all providers run as Claude Code, there is only **one config target**: `~/.claude/`. Profiles are named sets of agents, commands, hooks, MCP servers, and CLAUDE.md additions that get symlinked into `~/.claude/` for a given project type. Unloading removes the symlinks.

No per-tool config directories needed. One profile format for everything.

### Directory Structure

```
~/.ai-profiles/
  base/                         # always loaded — essentials for every project
    CLAUDE.md                   # global baseline instructions
    settings.json               # base MCP servers + hooks
    commands/                   # slash commands active in all sessions
    agents/                     # agents active in all sessions

  fullstack/                    # web/fullstack project set
    CLAUDE.md                   # appended to base on load
    settings.json               # additional MCP (DB, browser, etc.)
    commands/
    agents/

  ml/                           # ML / data pipeline set
  game/                         # game dev set
  devops/                       # infra / CI set
  ...

  orchestrator/
    models.yaml                 # model registry: strengths, limits, ccs command
    routing.yaml                # task type → model routing rules
    usage/                      # daily/rolling usage logs per ccs profile
      2026-03-29/
        claude.log
        backup.log
        gemini.log
        codex.log
    queue/                      # pending tasks blocked by limit
    checkpoints/                # partial task state for resume on fallback
```

### `ai-profile` Script Interface

```bash
ai-profile load fullstack        # symlink fullstack set into ~/.claude/
ai-profile unload fullstack      # remove symlinks, restore base
ai-profile status                # show active profiles
ai-profile list                  # list available profiles
```

### How Loading Works

```bash
# Symlink agents from profile into ~/.claude/agents/
# Prefix prevents collision between profiles: {profile}__{filename}
ln -s ~/.ai-profiles/fullstack/agents/react-agent.md \
      ~/.claude/agents/fullstack__react-agent.md

# CLAUDE.md: concatenate base + profile → write to ~/.claude/CLAUDE.md
cat ~/.ai-profiles/base/CLAUDE.md \
    ~/.ai-profiles/fullstack/CLAUDE.md \
    > ~/.claude/CLAUDE.md

# settings.json: deep-merge base + profile MCP/hooks
```

Active state tracked in `~/.ai-profiles/.active`:
```
profiles: base fullstack
```

---

## Part 3 — Task Orchestrator

### Model Registry (`models.yaml`)

```yaml
models:
  claude:
    cmd: ccs
    strengths: [architecture, reasoning, review, debugging, tests]
    limits:
      type: rolling_hours
      window_hours: 5
    failover: backup

  backup:
    cmd: ccs backup
    strengths: [architecture, reasoning, review, debugging, tests]
    limits:
      type: rolling_hours
      window_hours: 5
    failover: deepseek

  gemini:
    cmd: ccs gemini
    strengths: [large_context, web_research, docs, file_analysis]
    limits:
      type: daily_requests
      max: 1000

  codex:
    cmd: ccs codex
    strengths: [code_gen, scaffolding, boilerplate, pr]
    limits:
      type: oauth_session

  deepseek:
    cmd: ccs deepseek
    strengths: [planning, reasoning_chain, analysis]
    limits:
      type: api_budget

  glm:
    cmd: ccs glm
    strengths: [cost_optimized, repetitive, formatting]
    limits:
      type: api_budget

  km:
    cmd: ccs km
    strengths: [long_context, summarization]
    limits:
      type: api_budget

  openrouter:
    cmd: ccs openrouter
    strengths: [flexible, fallback, minimax]
    limits:
      type: api_budget
      budget_usd: 25
```

### Routing Rules (`routing.yaml`)

```yaml
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

  - match: [research, web, latest, version, changelog]
    primary: gemini
    fallback: claude

  - match: [repetitive, format, lint, rename, migrate]
    primary: glm
    fallback: openrouter
```

### `ai-do` Orchestrator Flow

```
ai-do "implement JWT auth for the API"

  Step 1: Keyword extraction
    → tokens: [implement, JWT, auth] → type: code_gen
    → primary: codex, fallback: claude

  Step 2: Availability check
    → codex: OAuth session active → AVAILABLE
    → proceed with codex

  Step 3: Profile load
    → ai-profile load fullstack (if not already active)

  Step 4: Execute
    → ccs codex --dangerously-skip-permissions
    → prompt injected via stdin or --print flag

  Step 5: Track usage
    → append to ~/.ai-profiles/orchestrator/usage/2026-03-29/codex.log

  Step 6: Done — result in .aim/results/<task_id>.json
```

When a limit is hit mid-task:
```
  → Detect quota error signal
  → Write checkpoint: { completed: [...], remaining: "..." }
  → Re-route to fallback (e.g. codex → claude → backup)
  → Resume: ccs backup with checkpoint context
```

### Script Interface

```bash
ai-do "implement the user dashboard"          # auto-assign
ai-do --model gemini "analyze entire src/"    # force model
ai-do --split "build full auth feature"       # split subtasks across models
ai-do --dry-run "write unit tests"            # show routing without executing
ai-status                                     # usage dashboard
```

### `ai-status` Dashboard

```
Model         Limit Type     Used        Remaining    Status
──────────────────────────────────────────────────────────
claude        5h rolling     2.3h        2.7h         OK
backup        5h rolling     0h          5h           OK
gemini        1000/day       340         660          OK
codex         OAuth          —           active       OK
deepseek      API budget     $1.20       ~$18.80      OK
glm           API budget     $0.40       ~budget      OK
openrouter    API budget     $2.10       $22.90       OK

Active profile: fullstack
```

---

## Part 4 — Relationship to 05-subagents

The `05-subagents` orchestrator pattern (`orchestrator` → `task-runner` → external CLIs) is still valid but needs one correction: instead of shelling out to native CLIs (`gemini -p`, `qwen -p`, `codex exec`), `task-runner` should invoke CCS profiles:

```bash
# OLD (inconsistent — each CLI behaves differently)
gemini -p "implement auth"
qwen --approval-mode full-auto -p "implement auth"

# NEW (consistent — all run as Claude Code, same behavior)
ccs gemini --dangerously-skip-permissions
ccs qwen --dangerously-skip-permissions
```

The `.aim/` continuity structure, `team.json` roster, and result files remain unchanged — only the invocation changes. Continuity is stronger because all models share the same CLAUDE.md and `.aim/` state.

---

## Part 5 — Build Roadmap

| Phase | What gets built | Commands delivered |
|---|---|---|
| 1 | Profile loader: symlink/merge/concatenate into `~/.claude/` | `ai-profile load/unload/status/list` |
| 2 | Usage tracker per CCS profile (rolling + daily + budget) | Internal to orchestrator |
| 3 | `ai-do`: keyword extraction → model routing → CCS invocation | `ai-do`, `ai-do --model`, `ai-do --dry-run` |
| 4 | Checkpoint/resume + failover chain on limit hit | Automatic within `ai-do` |
| 5 | `ai-status` dashboard, `ai-do --split` for parallel subtasks | `ai-status`, `ai-do --split` |
| 6 | Update 05-subagents `task-runner` to use CCS invocation | Patch to `task-runner.md` |

---

## Quick Reference

```bash
# Set up CCS accounts
ccs auth create main
ccs auth create backup

# Load a project profile
ai-profile load fullstack

# Assign a task — orchestrator picks the model
ai-do "implement the user dashboard"

# Check quota and active profiles
ai-status

# Force a specific model
ai-do --model gemini "analyze the entire src/ directory"

# Preview routing without running
ai-do --dry-run "write unit tests for auth module"

# Launch a specific provider manually
ccs gemini --dangerously-skip-permissions
ccs deepseek --dangerously-skip-permissions
```
