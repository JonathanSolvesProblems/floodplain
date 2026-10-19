from floodplain.repos import SourceRef
from floodplain.sandbox import Experiment, RunOutcome, parse_junit, parse_resolved

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="1" failures="1" skipped="1" tests="4">
<testcase classname="tests.test_a" name="test_ok" time="0.001" />
<testcase classname="tests.test_a" name="test_bad" time="0.001"><failure message="assert 1 == 2">boom</failure></testcase>
<testcase classname="tests.test_b" name="test_skip" time="0.0"><skipped type="pytest.skip" message="no key" /></testcase>
<testcase classname="tests.test_c" name="tests/test_c.py" time="0.0"><error message="collection failure">ImportError: No module named httpx</error></testcase>
</testsuite></testsuites>"""


def test_parse_junit_statuses():
    tests, collection = parse_junit(JUNIT)
    assert tests["tests.test_a::test_ok"] == "passed"
    assert tests["tests.test_a::test_bad"] == "failed"
    assert tests["tests.test_b::test_skip"] == "skipped"
    assert tests["tests.test_c::tests/test_c.py"] == "error"
    assert collection == ["tests.test_c::tests/test_c.py"]


def test_parse_resolved():
    out = "[floodplain] resolved:\nopenai==2.34.0\nhttpx==0.28.1\n"
    assert parse_resolved(out) == {"openai": "2.34.0", "httpx": "0.28.1"}


def _outcome(label, tests, collection=(), install_exit=0):
    return RunOutcome(label=label, cutoff="x", install_exit=install_exit, install_tail="",
                      test_exit=0, test_tail="", tests=tests, collection_errors=list(collection))


def _exp(before, after):
    return Experiment("dep", "1.0", SourceRef("o", "r", "v1.0", "abc"), before=before, after=after)


def test_verdict_broken_when_passing_test_starts_failing():
    exp = _exp(_outcome("before", {"t::a": "passed", "t::b": "failed"}),
               _outcome("after", {"t::a": "failed", "t::b": "failed"}))
    v = exp.verdict()
    assert v["status"] == "broken" and v["newly_failing"] == ["t::a"] and v["pre_existing_failures"] == 1


def test_verdict_ignores_pre_existing_failures():
    exp = _exp(_outcome("before", {"t::a": "passed", "t::b": "failed"}),
               _outcome("after", {"t::a": "passed", "t::b": "failed"}))
    assert exp.verdict()["status"] == "ok"


def test_verdict_broken_on_new_collection_error():
    exp = _exp(_outcome("before", {"t::a": "passed"}),
               _outcome("after", {}, collection=["tests/test_x.py"]))
    v = exp.verdict()
    assert v["status"] == "broken" and v["new_collection_errors"] == ["tests/test_x.py"]


def test_verdict_broken_when_install_fails_only_after():
    exp = _exp(_outcome("before", {"t::a": "passed"}), _outcome("after", {}, install_exit=1))
    assert exp.verdict()["kind"] == "install"


def test_verdict_unrunnable_when_both_installs_fail():
    exp = _exp(_outcome("before", {}, install_exit=1), _outcome("after", {}, install_exit=1))
    assert exp.verdict()["status"] == "unrunnable"
