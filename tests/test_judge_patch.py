from floodplain.fixer import judge_patch

BEFORE = {"t::a": "passed", "t::b": "passed", "t::c": "failed"}


def test_a_suite_that_still_cannot_collect_is_not_verified():
    # The bug this guards: the old check excluded still-collecting-error targets from the
    # still-failing list, so this exact case came back "verified" with pytest exit 2.
    v = judge_patch(2, {}, ["tests.mod::tests/mod.py"], {"new_collection_errors": ["tests.mod::tests/mod.py"]}, BEFORE)
    assert not v["verified"]
    assert any("exit 2" in r for r in v["reasons"])
    assert any("collect" in r for r in v["reasons"])


def test_interrupted_run_is_never_verified_even_if_targets_pass():
    tests = {"t::a": "passed", "t::b": "passed", "t::c": "failed"}
    v = judge_patch(2, tests, [], {"newly_failing": ["t::a"]}, BEFORE)
    assert not v["verified"]


def test_patch_that_restores_the_before_state_is_verified():
    tests = {"t::a": "passed", "t::b": "passed", "t::c": "failed"}  # c was failing before too
    v = judge_patch(1, tests, [], {"newly_failing": ["t::a"]}, BEFORE)
    assert v["verified"] and v["still_failing"] == [] and v["regressions"] == []


def test_fixing_the_target_but_breaking_another_test_is_a_regression():
    tests = {"t::a": "passed", "t::b": "failed", "t::c": "failed"}
    v = judge_patch(1, tests, [], {"newly_failing": ["t::a"]}, BEFORE)
    assert not v["verified"] and v["regressions"] == ["t::b"]


def test_a_test_that_vanished_counts_as_not_passing():
    tests = {"t::a": "passed"}  # t::b no longer reported at all
    v = judge_patch(0, tests, [], {"newly_failing": ["t::a"]}, BEFORE)
    assert not v["verified"] and "t::b" in v["still_failing"]


def test_patch_that_will_not_install_is_not_verified():
    v = judge_patch(41, {}, [], {"newly_failing": ["t::a"]}, BEFORE)
    assert not v["verified"] and any("install" in r for r in v["reasons"])
