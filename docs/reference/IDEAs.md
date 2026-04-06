# IDEAs — Continuous Autonomous Multi-Agent System

> Conversation export — 2026-03-31
> Context: `/home/hung/Videos/temp-2/` (ai-profile Phase 1) + architecture exploration
>
> **Note**: This is architecture exploration, not an implementation roadmap.
> The orchestration layers (Phases 2–6) have no code yet and no proven runtime path.
> Treat everything after Section 3 as speculative until Phase 1 is fully closed out.

---

## 1. What temp-2 is today (accurate)

`ai-profile` — core Phase 1 behavior is complete (44 tests passing); closeout tasks remain (install, smoke test, coverage). It is a **passive config injection layer**:

- Symlinks named profile sets (`agents/`, `commands/`, `skills/`, `hooks/`) into `~/.claude/`
- Deep-merges `settings.json` + concatenates `CLAUDE.md`
- Tracks active state in `~/.ai-profiles/.active`

**Current repo structure** (what actually exists):
```
src/ai_profile.py
tests/conftest.py, test_merge.py, test_symlinks.py, test_commands.py
scripts/scaffold-profiles.py
docs/plans/
```

No `orchestrator/`, `queue/`, `checkpoints/` exist in this repo. `scripts/scaffold-profiles.py` would create `~/.ai-profiles/orchestrator/...` in the **home directory** — not inside this repo. Running the script changes `~`, not the repo layout.

**One known code gap** (actionable now):

`symlink_profile` in `src/ai_profile.py:44` silently skips broken symlinks:
```python
if dst.is_symlink():
    continue
```
`is_symlink()` returns `True` for broken links too. A stale link from a deleted profile file blocks re-creation silently. Fix:
```python
if dst.is_symlink() and dst.exists():
    continue
if dst.is_symlink():   # broken — remove and re-create
    dst.unlink()
```
Also missing: a regression test for reload-after-broken-destination behavior.

---

## 2. The gap: what continuous execution needs

The "all-night agent team" scenario exposes things ai-profile doesn't have by design:

| Requirement | Status |
|---|---|
| Load correct toolset per project | Done (Phase 1) |
| Route task to best model | Not built |
| Detect external events (GitHub issue, test failure) | Not built |
| Queue tasks | Not built |
| Session continuity across tasks | Not designed |
| Know when a task is done | Not designed |
| Retry / failover on model limit | Not built |

---

## 3. Three tools and their roles

### smux (https://github.com/ShawnPana/smux)
**Runtime transport layer** via tmux panes.

Key primitive: `tmux-bridge type <pane> <task>` + `tmux-bridge read <pane> N`

- Fills session continuity: persistent named pane retains conversation across tasks
- Fills agent addressing: `tmux-bridge name/resolve` labels live panes
- **Does not fill**: config merging, model routing, event ingestion

### ralph-loop (https://claude.com/plugins/ralph-loop)
**Intra-session iteration loop.**

```
/ralph-loop "task" --max-iterations 10 --completion-promise "DONE"
```

- Provides a **stop condition**, not correctness verification: loops until the completion marker appears in output. Whether the output is actually correct depends on what the loop prompt checks (tests, CI, assertions). The marker alone is not proof of correctness.
- **Does not fill**: multi-agent dispatch, model failover, event ingestion

### ai-watch (not built, speculative)
**Event ingestion daemon** — would watch GitHub, filesystem, cron; write to queue.

Implementation note: Python stdlib has no clean cross-platform file watching.
- Linux: requires `inotify_simple` or `watchdog` (not stdlib)
- macOS: requires `kqueue`/`FSEvents` wrapper (not stdlib)
- Fallback: plain polling with `os.path.getmtime` — works everywhere, costs CPU
This is a real dependency, not a zero-cost stdlib solution.

---

## 4. Speculative architecture (exploration only)

These layers make sense conceptually but none are proven yet. No code exists for Layers 2–4.

```
Layer 4: Event Sources (GitHub, filesystem, cron, manual)
    ↓
Layer 3: ai-watch — event daemon (not built)
    ↓
Layer 2: ai-do — dispatcher via smux panes (not built)
    ↓
Layer 1: ai-profile — core behavior complete; closeout tasks remain
    ↓
Layer 0: smux pane pool — persistent ccs <model> panes (not initialized)
         ralph-loop runs inside each pane
```

### On checkpoints vs pane history

These are not interchangeable:

| | tmux pane history | File checkpoint |
|---|---|---|
| Survives tmux session kill | No | Yes |
| Survives reboot | No | Yes |
| Human-inspectable | No | Yes |
| Available immediately | Yes | Requires write |

Pane history reduces *what* needs checkpointing (no need to re-send completed work), but doesn't replace checkpoints for crash recovery. Both may be needed; they serve different failure modes.

---

## 5. Immediate next steps (grounded in current code)

These are the only things that should be called "next steps" right now:

1. **Fix broken-symlink gap** in `src/ai_profile.py:44`
2. **Add regression test**: `test_symlink_recreates_after_broken_destination`
3. **Phase 1 closeout tasks** (core behavior done; these finish the phase):
   - Install `~/.claude/bin/ai-profile` + `~/.local/bin/` symlink
   - Run `scripts/scaffold-profiles.py` smoke test
   - Coverage check — requires `uv pip install pytest-cov` first
4. **If runtime orchestration**: prove one minimal flow first — single dispatcher + one persistent session mechanism — before adding ai-watch, checkpointing, and dashboards

---

## 6. Revised build phases (honest sequencing)

| Phase | What | Prerequisite |
|---|---|---|
| 1 | ai-profile — core behavior complete (44 tests); closeout tasks remain | — |
| 1.1 | Fix broken-symlink + test | Phase 1 |
| 2 | Prove minimal dispatcher: one command → one smux pane | Phase 1.1 |
| 3 | Usage tracker (simple append log) | Phase 2 |
| 4 | ai-watch event daemon (with real watchdog dep) | Phase 3 |
| 5 | ai-do full dispatcher + routing.yaml | Phase 4 |
| 6 | Checkpoints for crash recovery | Phase 5 |
| 7 | ai-status dashboard | Phase 6 |
