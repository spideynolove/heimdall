from ai_profile import merge_settings, build_claude_md


def test_merge_empty_overlay():
    base = {"permissions": ["Bash(git:*)"], "hooks": {"PostToolUse": []}}
    result = merge_settings(base, {})
    assert result == base


def test_merge_array_concatenation():
    base = {"hooks": {"PostToolUse": [{"command": "a.sh"}]}}
    overlay = {"hooks": {"PostToolUse": [{"command": "b.sh"}]}}
    result = merge_settings(base, overlay)
    assert result["hooks"]["PostToolUse"] == [
        {"command": "a.sh"}, {"command": "b.sh"}
    ]


def test_merge_array_dedup_by_command():
    base = {"hooks": {"PostToolUse": [{"command": "a.sh"}]}}
    overlay = {"hooks": {"PostToolUse": [{"command": "a.sh"}, {"command": "b.sh"}]}}
    result = merge_settings(base, overlay)
    assert result["hooks"]["PostToolUse"] == [
        {"command": "a.sh"}, {"command": "b.sh"}
    ]


def test_merge_mcp_servers_dedup_by_key():
    base = {"mcpServers": {"sqlite": {"command": "sqlite-mcp"}}}
    overlay = {"mcpServers": {"sqlite": {"command": "sqlite-mcp-new"}, "pg": {"command": "pg-mcp"}}}
    result = merge_settings(base, overlay)
    assert set(result["mcpServers"].keys()) == {"sqlite", "pg"}


def test_merge_scalar_overlay_wins():
    base = {"effortLevel": "low"}
    overlay = {"effortLevel": "high"}
    result = merge_settings(base, overlay)
    assert result["effortLevel"] == "high"


def test_merge_permissions_dedup():
    base = {"permissions": ["Bash(git:*)", "Bash(npm:*)"]}
    overlay = {"permissions": ["Bash(npm:*)", "Bash(docker:*)"]}
    result = merge_settings(base, overlay)
    assert sorted(result["permissions"]) == sorted(["Bash(git:*)", "Bash(npm:*)", "Bash(docker:*)"])


def test_build_claude_md_base_only(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "CLAUDE.md").write_text("# Base\n")
    assert build_claude_md(tmp_path, []) == "# Base\n"


def test_build_claude_md_with_profile(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "CLAUDE.md").write_text("# Base\n")
    (tmp_path / "fullstack").mkdir()
    (tmp_path / "fullstack" / "CLAUDE.md").write_text("# Fullstack\n")
    result = build_claude_md(tmp_path, ["fullstack"])
    assert "# Base\n" in result
    assert "# Profile: fullstack" in result
    assert "# Fullstack\n" in result


def test_build_claude_md_base_in_active_not_duplicated(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "CLAUDE.md").write_text("# Base\n")
    result = build_claude_md(tmp_path, ["base"])
    assert result.count("# Base") == 1


def test_build_claude_md_profile_without_claude_md(tmp_path):
    (tmp_path / "base").mkdir()
    (tmp_path / "base" / "CLAUDE.md").write_text("# Base\n")
    (tmp_path / "vue").mkdir()
    result = build_claude_md(tmp_path, ["vue"])
    assert result == "# Base\n"


def test_build_claude_md_missing_base_warns(tmp_path, capsys):
    (tmp_path / "fullstack").mkdir()
    (tmp_path / "fullstack" / "CLAUDE.md").write_text("# Fullstack\n")
    result = build_claude_md(tmp_path, ["fullstack"])
    captured = capsys.readouterr()
    assert "warning" in (captured.out + captured.err).lower()
    assert "# Fullstack\n" in result
