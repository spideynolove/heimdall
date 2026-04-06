# ai-profile Phase 1 Design

**Date:** 2026-03-29
**Scope:** Phase 1 of ai-cli-orchestration.md — profile loader only

---

## What gets built

`ai-profile` — a Python (stdlib-only) CLI that symlinks named profile sets into `~/.claude/`, enabling project-type-specific agents, commands, skills, and hooks to be loaded and unloaded on demand.

---

## File locations

```
~/.claude/bin/ai-profile          Python script, chmod +x
~/.local/bin/ai-profile           symlink → ~/.claude/bin/ai-profile

~/.ai-profiles/
  .active                         space-separated list of currently loaded profiles
  base/                           always-present essentials
  fullstack/
  vue/
  ml/
  backend-go/
  backend-rust/
  trading/
  devops/
  automation/
  refactor/
  orchestrator/
    models.yaml                   Phase 3 placeholder stub
    routing.yaml                  Phase 3 placeholder stub
    usage/
    queue/
    checkpoints/
```

Each profile dir contains only the subdirs it contributes:

| Profile      | agents/ | commands/ | skills/ | hooks/ |
|--------------|---------|-----------|---------|--------|
| base         | ✓       | ✓         | ✓       | ✓      |
| fullstack    | ✓       | ✓         | ✓       | ✓      |
| vue          |         |           | ✓       |        |
| ml           | ✓       |           |         |        |
| backend-go   | ✓       |           |         |        |
| backend-rust | ✓       |           |         |        |
| trading      | ✓       |           | ✓       |        |
| devops       |         | ✓         |         | ✓      |
| automation   | ✓       | ✓         |         | ✓      |
| refactor     | ✓       |           |         |        |

---

## Commands

```
ai-profile load <name>     load a profile
ai-profile unload <name>   unload a profile
ai-profile status          show active profiles and their contributions
ai-profile list            list all available profiles
```

---

## Load behavior

1. Symlink every file in `profile/agents/` → `~/.claude/agents/<name>__<filename>`
2. Symlink every file in `profile/commands/` → `~/.claude/commands/<name>__<filename>`
3. Symlink every file in `profile/skills/` → `~/.claude/skills/<name>__<filename>` (recursive)
4. Symlink every file in `profile/hooks/` → `~/.claude/hooks/<name>__<filename>`
5. Concatenate CLAUDE.md: `base/CLAUDE.md` + each active profile's CLAUDE.md in load order,
   separated by `\n---\n# Profile: <name>\n`, written to `~/.claude/CLAUDE.md`
6. Deep-merge settings.json: base + each active profile's settings.json in load order,
   written to `~/.claude/settings.json`
7. Append `<name>` to `~/.ai-profiles/.active`
8. Idempotent: loading an already-active profile is a no-op with a message

---

## Unload behavior

1. Remove all `~/.claude/**/<name>__*` symlinks
2. Remove `<name>` from `.active`
3. Rewrite `~/.claude/CLAUDE.md` from scratch: base + remaining active profiles in original load order
4. Rewrite `~/.claude/settings.json` from scratch: base + remaining active profiles in original load order
5. Unloading an inactive profile warns and exits cleanly

---

## settings.json merge rules

- Arrays: concatenated, then deduplicated by stable key
  - hooks: deduplicate by `command` value
  - mcpServers: deduplicate by server name key
- Objects: merged by key (later profile wins on conflict)
- Scalars: later profile overwrites base

---

## CLAUDE.md merge format

```
<base CLAUDE.md content>

---
# Profile: fullstack
<fullstack CLAUDE.md content>

---
# Profile: vue
<vue CLAUDE.md content>
```

---

## Error handling

| Situation | Behavior |
|---|---|
| Profile dir not found | `error: profile 'X' not found` → exit 1 |
| Broken symlink on unload | skip silently, continue |
| settings.json parse error | abort, leave existing file untouched |
| `~/.claude/CLAUDE.md` missing base | warn, write from profile only |
| Load already-active profile | no-op + message |
| Unload inactive profile | warn + exit 0 |

---

## Profile skeleton (Phase 1 initial content)

Each profile gets:
- `CLAUDE.md` stub: `# Profile: <name>\n`
- `settings.json` stub: `{}`
- Subdirectory structure per table above (empty dirs)

`orchestrator/models.yaml` and `orchestrator/routing.yaml` created as minimal stubs for Phase 3.

---

## Out of scope (Phase 2+)

- `ai-do` task orchestrator
- `ai-status` dashboard
- Usage tracking
- Checkpoint/resume on limit hit
- `ai-do --split` parallel subtasks
