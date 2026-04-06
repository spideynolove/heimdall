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
    models_yaml.write_text(
        "models:\n"
        "  claude:\n"
        "    model: claude-sonnet-4-6\n"
        "    proxy: \"\"\n"
        "    strengths: [architecture, reasoning, review, debugging, tests]\n"
        "    failover: backup\n"
        "  backup:\n"
        "    model: claude-sonnet-4-6\n"
        "    proxy: \"\"\n"
        "    strengths: [architecture, reasoning, review, debugging, tests]\n"
        "    failover: deepseek\n"
        "  gemini:\n"
        "    model: gemini-2.5-pro\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [large_context, web_research, docs, file_analysis]\n"
        "  codex:\n"
        "    model: gpt-4o\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [code_gen, scaffolding, boilerplate, pr]\n"
        "  deepseek:\n"
        "    model: deepseek-r1\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [planning, reasoning_chain, analysis]\n"
        "  glm:\n"
        "    model: glm-4\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [cost_optimized, repetitive, formatting]\n"
        "  km:\n"
        "    model: kimi-k2\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [long_context, summarization]\n"
        "  openrouter:\n"
        "    model: openrouter/auto\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [flexible, fallback]\n"
        "  qwen:\n"
        "    model: qwen-coder\n"
        "    proxy: http://localhost:8317\n"
        "    strengths: [code_gen, multilingual]\n"
    )

routing_yaml = orc / "routing.yaml"
if not routing_yaml.exists():
    routing_yaml.write_text(
        "rules:\n"
        "  - match: [architecture, planning, design, system, schema]\n"
        "    primary: deepseek\n"
        "    fallback: claude\n"
        "  - match: [implement, generate, scaffold, boilerplate, crud, feature]\n"
        "    primary: codex\n"
        "    fallback: claude\n"
        "  - match: [analyze, scan, codebase, large_context, all_files]\n"
        "    primary: gemini\n"
        "    fallback: km\n"
        "  - match: [review, debug, fix, security, test]\n"
        "    primary: claude\n"
        "    fallback: backup\n"
        "  - match: [docs, readme, translate, comment, multilingual]\n"
        "    primary: glm\n"
        "    fallback: openrouter\n"
        "  - match: [research, web, latest, version, changelog]\n"
        "    primary: gemini\n"
        "    fallback: claude\n"
        "  - match: [repetitive, format, lint, rename, migrate]\n"
        "    primary: glm\n"
        "    fallback: openrouter\n"
    )

print("~/.ai-profiles/ scaffold complete")
