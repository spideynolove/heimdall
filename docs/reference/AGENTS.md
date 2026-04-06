# Repository Guidelines

## Project Structure & Module Organization

This repository is a small Python CLI project for managing AI profile overlays. The main implementation lives in `src/ai_profile.py`. Tests live in `tests/` and cover command behavior, settings merging, and symlink management. Helper scripts live in `scripts/`, including `scripts/scaffold-profiles.py` for creating a local `~/.ai-profiles` scaffold. Keep new Python modules under `src/` and place focused test coverage beside the existing pytest suite in `tests/`.

## Build, Test, and Development Commands

Activate the shared local environment before running Python commands:

- `source /home/hung/env/.venv/bin/activate`

Useful commands from the repository root:

- `python -m pytest`
- `python -m pytest tests/test_commands.py`
- `python -m pytest tests/test_merge.py tests/test_symlinks.py`
- `python src/ai_profile.py list`
- `python src/ai_profile.py status`
- `python scripts/scaffold-profiles.py`

If you need new dependencies, install them with `uv pip install ...` and update `pyproject.toml`.

## Coding Style & Naming Conventions

Target Python 3.8+ as declared in `pyproject.toml`. Follow the existing style in `src/ai_profile.py`: small functions, explicit `Path` usage, and straightforward standard-library-first implementation. Use `snake_case` for functions and variables, and keep CLI-facing messages concise and stable because tests assert against output text.

## Testing Guidelines

Run `python -m pytest` after changing behavior. Add or update tests in `tests/` for any CLI, merge, or filesystem behavior change. Prefer isolated tmp-path based fixtures, matching the current test style, rather than relying on real home-directory state. When changing command output, verify the affected assertions in `tests/test_commands.py`.

## Commit & Pull Request Guidelines

Use short, imperative commit subjects such as `Fix profile unload handling` or `Add settings merge coverage`. Pull requests should summarize behavior changes, call out any CLI output changes, and mention the verification command you ran.

## Scope Notes

Keep the project focused on profile management for Claude-style directories and profile overlays. Do not add speculative tooling or package structure unless it directly supports the CLI, profile scaffold script, or test coverage already present in this repository.
