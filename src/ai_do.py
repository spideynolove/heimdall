#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import re as _re
import sys
import urllib.request as _urllib
from pathlib import Path

import ai_dispatch


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text()) or {}
    except ImportError:
        print("error: pyyaml required — run: uv pip install pyyaml", file=sys.stderr)
        sys.exit(1)


def _tokenise(text: str) -> set[str]:
    return set(_re.split(r'[^a-z0-9_]+', text.lower()))


def route(task: str, rules: list[dict]) -> tuple[str, str]:
    tokens = _tokenise(task)
    for rule in rules:
        if tokens & set(rule.get("match", [])):
            return rule.get("primary", "claude"), rule.get("fallback", "backup")
    return "claude", "backup"


def get_model(name: str, models: dict) -> dict | None:
    return models.get(name)


def get_model_cmd(name: str, models: dict) -> tuple[str, str]:
    m = models.get(name)
    if m:
        return m.get("model", ""), m.get("proxy", "")
    return "", ""


def _load_routing(models_path: Path | None, routing_path: Path | None):
    orc_dir = Path(os.environ.get("AI_PROFILES_DIR", Path.home() / ".ai-profiles")) / "orchestrator"
    if models_path is None:
        models_path = orc_dir / "models.yaml"
    if routing_path is None:
        routing_path = orc_dir / "routing.yaml"
    data_models = load_yaml(models_path).get("models", {})
    data_routing = load_yaml(routing_path).get("rules", [])
    return data_models, data_routing, models_path, routing_path


def dispatch_task(
    task: str,
    models_path: Path | None = None,
    routing_path: Path | None = None,
    force_model: str = "",
    dry_run: bool = False,
    session: str = "ai-do",
) -> str:
    data_models, data_routing, models_path, routing_path = _load_routing(models_path, routing_path)

    if force_model:
        primary = force_model
        fallback = (data_models.get(primary) or {}).get("failover", "backup")
    else:
        primary, fallback = route(task, data_routing)

    alias, proxy = get_model_cmd(primary, data_models)

    if dry_run:
        print(f"[dry-run] task: {task!r}")
        print(f"[dry-run] primary: {primary}  fallback: {fallback}")
        print(f"[dry-run] model: {alias or '(default)'}  proxy: {proxy or '(direct)'}")
        return ""

    profiles_dir = Path(os.environ.get("AI_PROFILES_DIR", Path.home() / ".ai-profiles"))
    profile = primary if (profiles_dir / primary).is_dir() else ""

    return ai_dispatch.dispatch(
        task,
        profile=profile,
        session=session,
        model_alias=alias,
        proxy_url=proxy,
    )


def dispatch_split(
    tasks: list[str],
    models_path: Path | None = None,
    routing_path: Path | None = None,
    session: str = "ai-do",
) -> list[str]:
    data_models, data_routing, _, _ = _load_routing(models_path, routing_path)
    subtasks = []
    for task in tasks:
        primary, _ = route(task, data_routing)
        alias, proxy = get_model_cmd(primary, data_models)
        subtasks.append((task, alias, proxy))
    return ai_dispatch.dispatch_many(subtasks, session=session)


def notify(message: str) -> None:
    webhook = os.environ.get("AI_NOTIFY_WEBHOOK", "")
    if not webhook:
        return
    try:
        if webhook.startswith("telegram:"):
            _, token, chat_id = webhook.split(":", 2)
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
        else:
            url = webhook
            payload = json.dumps({"content": message}).encode()
        req = _urllib.Request(url, data=payload, headers={"Content-Type": "application/json"})
        _urllib.urlopen(req, timeout=5)
    except Exception:
        pass


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] != "run":
        print(
            "usage: ai-do run <task> [--model <name>] [--dry-run] [--split] [--session <name>]",
            file=sys.stderr,
        )
        sys.exit(1)
    args = args[1:]
    task = ""
    force_model = ""
    dry_run = False
    split = False
    session = os.environ.get("AI_DISPATCH_SESSION", "ai-do")
    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            force_model = args[i + 1]
            i += 2
        elif args[i] == "--session" and i + 1 < len(args):
            session = args[i + 1]
            i += 2
        elif args[i] == "--dry-run":
            dry_run = True
            i += 1
        elif args[i] == "--split":
            split = True
            i += 1
        elif not task:
            task = args[i]
            i += 1
        else:
            i += 1
    if not task:
        print("error: task string required", file=sys.stderr)
        sys.exit(1)
    if split:
        tasks = [t.strip() for t in task.split(",") if t.strip()]
        try:
            results = dispatch_split(tasks, session=session)
            for idx, result in enumerate(results):
                if result:
                    print(f"[{idx}] {result}")
            notify(f"split done ({len(tasks)} tasks)")
        except Exception as err:
            notify(f"split failed: {err}")
            raise
    else:
        try:
            result = dispatch_task(task, force_model=force_model, dry_run=dry_run, session=session)
            if result:
                print(result)
                notify(f"done: {task[:60]}\n{result[:200]}")
        except Exception as err:
            notify(f"failed: {task[:60]}\n{err}")
            raise


if __name__ == "__main__":
    main()
