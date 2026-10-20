from floodplain.sandbox import CANDIDATE_DIR, install_script


def test_candidate_wheel_is_installed_after_the_test_deps_and_before_the_freeze():
    s = install_script(("test",), "2026-08-12T01:54:48Z", candidate="openai-3.0.0-py3-none-any.whl")
    step = f'uv pip install --quiet "{CANDIDATE_DIR}/openai-3.0.0-py3-none-any.whl"'
    assert step in s
    assert s.index("test deps installed from") < s.index(step) < s.index("resolved:")
    # the candidate's own dependencies still resolve inside the cutoff world
    assert s.index("UV_EXCLUDE_NEWER=2026-08-12T01:54:48Z") < s.index(step)
    assert "exit 43" in s


def test_no_candidate_means_no_candidate_step():
    assert CANDIDATE_DIR not in install_script(("test",), "2026-08-12T01:54:48Z")
