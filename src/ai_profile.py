#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

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
            if dst.is_symlink() and dst.exists():
                continue
            if dst.is_symlink():
                dst.unlink()
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


def build_claude_md(profiles_dir: Path, active: list[str]) -> str:
    base_path = profiles_dir / "base" / "CLAUDE.md"
    parts: list[str] = []
    if base_path.exists():
        parts.append(base_path.read_text())
    else:
        print("warning: base/CLAUDE.md not found", file=sys.stderr)
    for name in active:
        if name == "base":
            continue
        p = profiles_dir / name / "CLAUDE.md"
        if p.exists():
            parts.append(f"\n---\n# Profile: {name}\n")
            parts.append(p.read_text())
    return "".join(parts)


def get_active(profiles_dir: Path) -> list[str]:
    active_file = profiles_dir / ".active"
    if not active_file.exists():
        return []
    return [p for p in active_file.read_text().strip().split() if p]


def set_active(profiles_dir: Path, profiles: list[str]) -> None:
    (profiles_dir / ".active").write_text(" ".join(profiles))


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
            continue
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


_NON_PROFILE_DIRS = {"orchestrator"}


def cmd_status(profiles_dir: Path, claude_dir: Path) -> None:
    active = get_active(profiles_dir)
    if not active:
        print("no profiles active")
        return
    for i, name in enumerate(active):
        prefix = "\n" if i else ""
        print(f"{prefix}[{name}]")
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
