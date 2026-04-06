#!/usr/bin/env python3
from pathlib import Path

PROFILES_DIR = Path.home() / ".ai-profiles"

PROFILE_SUBDIRS = {
    "base":         ["commands", "skills", "hooks"],
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
        claude_md.write_text("")
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
