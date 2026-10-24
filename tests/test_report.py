from floodplain.report import best_patch, drop_generated, headline, render


def run(name, status, **kw):
    v = {"status": status, **kw.pop("verdict", {})}
    return {"dependent": name, "version": "1.0", "verdict": v,
            "before": {"summary": {"passed": 10}}, **kw}


def agent_trial(verified, rev=3, diff="diff --git a/pyproject.toml b/pyproject.toml\n+    \"httpx\",\n"):
    return {"verified": verified, "agent": True, "fixer_revision": rev,
            "attempts": [{"verified": verified, "diff": diff}],
            "steps": [{"tool": "read_file"}, {"tool": "run_tests"}, {"tool": "submit"}]}


def test_headline_counts_only_suites_the_release_reached():
    runs = [run("a", "broken"), run("b", "ok"), run("c", "held-back"), run("d", "no-tests")]
    assert headline(runs, "openai", "3.37.0") == "openai 3.37.0: 1 of the 2 working test suites broke"
    assert headline([run("b", "ok")], "openai", "3.37.0") == "openai 3.37.0: none of the 1 working test suites broke"


def test_the_patch_comes_from_the_most_reliable_revision_newest_on_a_tie():
    d = run("a", "broken", verdict={"newly_failing": ["t1", "t2"]},
            fix_trials=[agent_trial(True, rev=2), agent_trial(False), agent_trial(True)])
    won, k, n = best_patch(d)
    assert (k, n) == (1, 1) and won["fixer_revision"] == 2
    # a newer revision with no verified patch does not hide an older one that has one
    d["fix_trials"].append(agent_trial(False, rev=4))
    assert best_patch(d)[0]["fixer_revision"] == 2
    # equally reliable: the newer revision wins
    d["fix_trials"] = [agent_trial(True, rev=2), agent_trial(True), agent_trial(False, rev=4)]
    won, k, n = best_patch(d)
    assert (k, n) == (1, 1) and won["fixer_revision"] == 3
    md = render([d], target="openai", release="3.37.0", released_at="now")
    assert "1 of 1 independent agent runs" in md and "read_file, run_tests, submit" in md and "```diff" in md


def test_the_patch_shown_is_the_one_most_runs_agreed_on():
    pin = "diff --git a/pyproject.toml b/pyproject.toml\n-  \"openai\",\n+  \"openai<3\",\n"
    odd = "diff --git a/x.py b/x.py\n+client = httpx.Client()\n"
    d = run("a", "broken", fix_trials=[agent_trial(True, diff=odd), agent_trial(True, diff=pin),
                                       agent_trial(True, diff=pin.replace("  ", "    "))])
    won, k, n = best_patch(d)
    assert (k, n) == (3, 3) and "openai<3" in won["attempts"][0]["diff"]

    unverified = run("a", "broken", verdict={"newly_failing": ["t1"]}, fix_trials=[agent_trial(False)])
    md = render([unverified], target="openai", release="3.37.0", released_at="now")
    assert "No verified patch" in md and "```diff" not in md


def test_held_back_dependents_are_named_not_counted_as_passing():
    md = render([run("b", "ok"), run("c", "held-back")], target="openai", release="3.37.0", released_at="now")
    assert "Read clean (1):** b" in md and "Held back (1):** the release never reached" in md


def test_regenerated_build_metadata_is_not_part_of_the_patch():
    diff = ("diff --git a/pyproject.toml b/pyproject.toml\n+x\n"
            "diff --git a/pkg.egg-info/PKG-INFO b/pkg.egg-info/PKG-INFO\n+y\n")
    assert drop_generated(diff) == "diff --git a/pyproject.toml b/pyproject.toml\n+x\n"


def test_a_break_that_did_not_reproduce_is_named_as_flaky_not_counted():
    d = run("echo-agent", "ok", verdict={"was": "broken", "flaky_after": ["tests.t::slow_download"]})
    md = render([d, run("b", "ok")], target="openai", release="3.37.0", released_at="now")
    assert md.startswith("## openai 3.37.0: none of the 2 working test suites broke")
    assert "Not counted:** echo-agent had 1 test fail once" in md
