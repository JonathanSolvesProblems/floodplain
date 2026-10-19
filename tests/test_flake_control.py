from downstream.repos import SourceRef
from downstream.sandbox import Experiment, RunOutcome


def _outcome(label, tests, install_exit=0):
    return RunOutcome(label=label, cutoff="x", install_exit=install_exit, install_tail="",
                      test_exit=0, test_tail="", tests=tests)


def _exp(before, after, control=None):
    return Experiment("dep", "1.0", SourceRef("o", "r", "v1.0", "abc"),
                      before=before, after=after, control=control)


def test_flaky_test_is_not_reported_as_a_break():
    # t::flaky disagrees with itself across two identical "before" forks, so when it also
    # fails in "after" that is not evidence the release broke anything.
    exp = _exp(
        before=_outcome("before", {"t::flaky": "passed", "t::solid": "passed"}),
        after=_outcome("after", {"t::flaky": "failed", "t::solid": "passed"}),
        control=_outcome("control", {"t::flaky": "failed", "t::solid": "passed"}),
    )
    assert exp.flaky() == {"t::flaky"}
    assert exp.verdict()["status"] == "ok"


def test_real_break_still_reported_with_control_present():
    exp = _exp(
        before=_outcome("before", {"t::flaky": "passed", "t::solid": "passed"}),
        after=_outcome("after", {"t::flaky": "failed", "t::solid": "failed"}),
        control=_outcome("control", {"t::flaky": "failed", "t::solid": "passed"}),
    )
    v = exp.verdict()
    assert v["status"] == "broken"
    assert v["newly_failing"] == ["t::solid"]
    assert v["excluded_as_flaky"] == ["t::flaky"]
    assert v["flake_control"] is True


def test_without_control_nothing_is_excluded():
    exp = _exp(
        before=_outcome("before", {"t::a": "passed"}),
        after=_outcome("after", {"t::a": "failed"}),
    )
    v = exp.verdict()
    assert exp.flaky() == set()
    assert v["newly_failing"] == ["t::a"] and v["flake_control"] is False
