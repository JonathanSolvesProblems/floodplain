import pytest

from floodplain.repos import SourceRef
from floodplain.sandbox import GIT, clone_command


def test_every_git_call_carries_safe_directory():
    """The sandbox uid does not own the cloned tree, so a bare `git` call fails with
    'detected dubious ownership'. Setting it in config is not enough, because --global
    depends on HOME matching between image build and run."""
    tagged = clone_command(SourceRef("simonw", "llm", "0.32", "abc123"))
    sdist = clone_command(SourceRef("pypi", "x", None, None, sdist_url="https://example/x.tar.gz"))
    import re
    unguarded = re.compile(r"\bgit (?!-c safe\.directory)")
    for cmd in (tagged, sdist):
        assert not unguarded.search(cmd), f"unguarded git call in: {cmd}"
        assert GIT in cmd and "safe.directory" in cmd


def test_tagged_clone_checks_out_the_sha():
    cmd = clone_command(SourceRef("simonw", "llm", "0.32", "abc123"))
    assert "https://github.com/simonw/llm.git" in cmd
    assert "checkout --quiet 'abc123'" in cmd


def test_sdist_path_builds_a_git_repo_so_diffs_work():
    cmd = clone_command(SourceRef("pypi", "x", None, None, sdist_url="https://example/x.tar.gz"))
    assert "init -q" in cmd and "add -A" in cmd and "commit -qm sdist" in cmd


def test_no_source_raises():
    with pytest.raises(ValueError):
        clone_command(SourceRef("pypi", "x", None, None))
