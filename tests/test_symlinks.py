from ai_profile import symlink_profile, unsymlink_profile


def test_symlink_creates_prefixed_file_links(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    assert (claude_dir / "agents" / "fullstack__react-agent.md").is_symlink()
    assert (claude_dir / "commands" / "fullstack__e2e.md").is_symlink()


def test_symlink_creates_prefixed_dir_links_for_skills(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    link = claude_dir / "skills" / "fullstack__playwright"
    assert link.is_symlink()
    assert link.is_dir()


def test_symlink_points_to_correct_target(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    link = claude_dir / "agents" / "fullstack__react-agent.md"
    assert link.resolve() == (profile_a / "agents" / "react-agent.md").resolve()


def test_symlink_idempotent(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    symlink_profile("fullstack", profile_a, claude_dir)
    assert len(list((claude_dir / "agents").glob("fullstack__*"))) == 1


def test_unsymlink_removes_file_links(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    unsymlink_profile("fullstack", claude_dir)
    assert not (claude_dir / "agents" / "fullstack__react-agent.md").exists()


def test_unsymlink_removes_dir_links(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    unsymlink_profile("fullstack", claude_dir)
    assert not (claude_dir / "skills" / "fullstack__playwright").exists()


def test_unsymlink_skips_broken_links(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    (profile_a / "agents" / "react-agent.md").unlink()
    unsymlink_profile("fullstack", claude_dir)
    assert not list((claude_dir / "agents").glob("fullstack__*"))


def test_symlink_recreates_after_broken_destination(claude_dir, profile_a):
    symlink_profile("fullstack", profile_a, claude_dir)
    link = claude_dir / "agents" / "fullstack__react-agent.md"
    link.unlink()
    link.symlink_to("/nonexistent/path")
    symlink_profile("fullstack", profile_a, claude_dir)
    assert link.exists() and link.is_symlink()


def test_unsymlink_does_not_touch_other_profiles(claude_dir, profiles_dir):
    other = profiles_dir / "ml"
    (other / "agents").mkdir(parents=True)
    (other / "agents" / "python-reviewer.md").write_text("# ML\n")
    symlink_profile("ml", other, claude_dir)
    symlink_profile("fullstack", profiles_dir / "fullstack", claude_dir)
    unsymlink_profile("fullstack", claude_dir)
    assert (claude_dir / "agents" / "ml__python-reviewer.md").is_symlink()
