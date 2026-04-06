#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sys
import urllib.request
from pathlib import Path


def fetch_proxy_stats(proxy_base: str) -> dict:
    try:
        url = f"{proxy_base}/v0/management/usage"
        with urllib.request.urlopen(url, timeout=3) as resp:
            return json.loads(resp.read()) or {}
    except Exception:
        return {}


def show_models(models_path: Path) -> None:
    if not models_path.exists():
        print("models.yaml not found — run scaffold-profiles.py first")
        return
    try:
        import yaml
        data = yaml.safe_load(models_path.read_text()) or {}
    except ImportError:
        print("pyyaml required: uv pip install pyyaml")
        return
    models = data.get("models", {})
    if not models:
        print("no models configured")
        return
    print(f"{'Model':<12}  {'Alias':<24}  Proxy")
    print("─" * 60)
    for name, cfg in models.items():
        alias = cfg.get("model", "(default)")
        proxy = cfg.get("proxy", "") or "(direct)"
        print(f"{name:<12}  {alias:<24}  {proxy}")


def show_profiles(profiles_dir: Path) -> None:
    active_file = profiles_dir / ".active"
    if not active_file.exists():
        return
    active = [p for p in active_file.read_text().strip().split() if p]
    if not active:
        print("no profiles active")
        return
    print(f"active profiles: {' '.join(active)}")


def main() -> None:
    args = sys.argv[1:]
    proxy_base = os.environ.get("AI_PROXY_URL", "http://localhost:8317")
    profiles_dir = Path(os.environ.get("AI_PROFILES_DIR", Path.home() / ".ai-profiles"))
    models_path = profiles_dir / "orchestrator" / "models.yaml"

    only_proxy = "--proxy" in args
    only_profiles = "--profiles" in args

    if only_proxy:
        stats = fetch_proxy_stats(proxy_base)
        if stats:
            print(json.dumps(stats, indent=2))
        else:
            print(f"proxy at {proxy_base} unreachable or returned no data")
        return

    show_profiles(profiles_dir)
    print()
    show_models(models_path)

    if not only_profiles:
        print()
        stats = fetch_proxy_stats(proxy_base)
        if stats:
            print(f"proxy ({proxy_base}): {json.dumps(stats)}")
        else:
            print(f"proxy ({proxy_base}): offline or no data")


if __name__ == "__main__":
    main()
