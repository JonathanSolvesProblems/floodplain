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
