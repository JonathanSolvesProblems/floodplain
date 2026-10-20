from floodplain.sandbox import CANDIDATE_DIR, install_script


def test_candidate_is_offered_to_every_resolution_not_forced_on_top():
    s = install_script(("test",), "2026-08-12T01:54:48Z", candidate="openai-3.0.0-py3-none-any.whl")
    offer = f"export UV_FIND_LINKS={CANDIDATE_DIR}"
    assert offer in s
    # before the first resolution, so the base install, extras and groups all see it
    assert s.index(offer) < s.index("uv pip install --quiet -e .")
    # its dependencies still resolve inside the cutoff world
    assert s.index("UV_EXCLUDE_NEWER=2026-08-12T01:54:48Z") < s.index(offer)
    # never installed over an already-resolved environment: that keeps dropped dependencies
    assert f'uv pip install --quiet "{CANDIDATE_DIR}' not in s


def test_no_candidate_means_no_candidate_source():
    assert CANDIDATE_DIR not in install_script(("test",), "2026-08-12T01:54:48Z")


def test_a_verdict_counts_only_if_the_after_fork_installed_the_release():
    from floodplain.sandbox import attribute
    ok = {"status": "ok"}
    assert attribute(ok, {"resolved": {"openai": "3.0.0"}}, "openai", "3.0.0") == ok
    held = attribute(ok, {"resolved": {"openai": "2.54.0"}}, "openai", "3.0.0")
    assert held["status"] == "held-back" and held["was"] == "ok" and "2.54.0" in held["reason"]
    assert attribute(ok, {"resolved": {}}, "openai", "3.0.0")["reason"] == "the after fork never installed openai"
    # verdicts that never read the suite are left alone
    assert attribute({"status": "no-tests"}, {"resolved": {}}, "openai", "3.0.0") == {"status": "no-tests"}


def test_the_install_records_the_whole_freeze():
    s = install_script(("test",), "2026-08-12T01:54:48Z")
    assert "uv pip freeze\n" in s and "grep -iE '^(openai" not in s
