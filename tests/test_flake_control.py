from floodplain.repos import SourceRef
from floodplain.sandbox import Experiment, RunOutcome


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


def test_empty_after_fork_is_incomplete_not_ok():
    # The bug this guards: a transport error in the after fork returns no tests, so nothing
    # is "newly failing" and the run would otherwise be reported as "nothing broke".
    exp = _exp(
        before=_outcome("before", {f"t::{i}": "passed" for i in range(100)}),
        after=_outcome("after", {}),
    )
    v = exp.verdict()
    assert v["status"] == "incomplete" and v["kind"] == "no-results" and v["arm"] == "after"


def test_half_the_suite_vanishing_is_incomplete():
    exp = _exp(
        before=_outcome("before", {f"t::{i}": "passed" for i in range(100)}),
        after=_outcome("after", {f"t::{i}": "passed" for i in range(20)}),
    )
    v = exp.verdict()
    assert v["status"] == "incomplete" and v["collected_after"] == 20


def test_real_break_reports_coverage():
    before = {f"t::{i}": "passed" for i in range(100)}
    after = dict(before)
    after["t::1"] = "failed"
    v = _exp(_outcome("before", before), _outcome("after", after)).verdict()
    assert v["status"] == "broken"
    assert v["collected_before"] == 100 and v["collected_after"] == 100


def test_without_control_nothing_is_excluded():
    exp = _exp(
        before=_outcome("before", {"t::a": "passed"}),
        after=_outcome("after", {"t::a": "failed"}),
    )
    v = exp.verdict()
    assert exp.flaky() == set()
    assert v["newly_failing"] == ["t::a"] and v["flake_control"] is False
