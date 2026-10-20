import re

from floodplain.repos import SourceRef
from floodplain.sandbox import LOCATE_SCRIPT, Experiment, RunOutcome, install_script


def test_locate_script_embeds_the_package_name():
    s = install_script(("test",), "2026-08-12T01:54:48Z", package="livekit-agents")
    assert "PKG='livekit-agents'" in s
    # the normalised underscore form is derived in-shell, so both spellings match a pyproject
    assert "tr '-' '_'" in s
    # install and test both run from the located directory, not the repo root
    assert 'cd "$(cat /work/pkgdir)"' in s


def test_locate_script_falls_back_to_repo_root():
    assert "FOUND=/work/repo" in LOCATE_SCRIPT


def test_locate_regex_matches_real_pyproject_name_lines():
    # The shell uses a POSIX ERE; mirror it here so a change to one is caught by the other.
    pkg, pkgu = "livekit-agents", "livekit_agents"
    pattern = re.compile(
        rf"^[ \t]*(name|NAME)[ \t]*=[ \t]*[\"']?({pkg}|{pkgu})[\"']?[ \t]*,?[ \t]*$",
        re.IGNORECASE | re.MULTILINE,
    )
    assert pattern.search('name = "livekit-agents"')
    assert pattern.search("name = 'livekit_agents'")
    assert pattern.search("    name='livekit-agents',")
    assert not pattern.search('name = "livekit-agents-extras"')
    assert not pattern.search('dependencies = ["livekit-agents"]')


def _outcome(label, install_exit=0, test_exit=0):
    return RunOutcome(label=label, cutoff="x", install_exit=install_exit, install_tail="",
                      test_exit=test_exit, test_tail="", tests={})


def test_timeout_is_its_own_status_not_unrunnable():
    exp = Experiment("dep", "1.0", SourceRef("o", "r", "v1", "s"),
                     before=_outcome("before", install_exit=124),
                     after=_outcome("after", install_exit=0))
    assert exp.verdict()["status"] == "timed-out"


def test_install_failure_both_sides_is_unrunnable_with_evidence():
    exp = Experiment("dep", "1.0", SourceRef("o", "r", "v1", "s"),
                     before=_outcome("before", install_exit=41),
                     after=_outcome("after", install_exit=41))
    v = exp.verdict()
    assert v["status"] == "unrunnable" and "evidence" in v
