from datetime import UTC, datetime

from downstream.pypi import declared_deps, normalize, version_at


def _project(releases: dict[str, list[dict]]) -> dict:
    return {"releases": releases}


def test_normalize():
    assert normalize("Foo_Bar.baz") == "foo-bar-baz"
    assert normalize("OpenAI") == "openai"


def test_version_at_picks_latest_before_cutoff():
    project = _project({
        "1.0.0": [{"upload_time": "2026-01-01T00:00:00", "yanked": False}],
        "1.1.0": [{"upload_time": "2026-06-01T00:00:00", "yanked": False}],
        "2.0.0": [{"upload_time": "2026-08-12T02:00:00", "yanked": False}],
    })
    when = datetime(2026, 8, 12, 1, 55, 48, tzinfo=UTC)
    assert version_at(project, when) == "1.1.0"


def test_version_at_skips_prerelease_and_yanked():
    project = _project({
        "1.0.0": [{"upload_time": "2026-01-01T00:00:00", "yanked": False}],
        "1.1.0rc1": [{"upload_time": "2026-02-01T00:00:00", "yanked": False}],
        "1.2.0": [{"upload_time": "2026-03-01T00:00:00", "yanked": True}],
    })
    when = datetime(2026, 8, 1, tzinfo=UTC)
    assert version_at(project, when) == "1.0.0"


def test_version_at_uses_last_file_upload():
    # A release whose wheel landed after the cutoff was not installable in full before it.
    project = _project({
        "1.0.0": [
            {"upload_time": "2026-08-11T00:00:00", "yanked": False},
            {"upload_time": "2026-08-13T00:00:00", "yanked": False},
        ],
    })
    when = datetime(2026, 8, 12, tzinfo=UTC)
    assert version_at(project, when) is None


def test_declared_deps_extra_detection():
    deps = declared_deps([
        "openai>=1.0",
        'openai>=2; extra == "llm"',
        'httpx<1; python_version < "3.9"',
        "not a requirement !!!",
    ])
    assert [(d.name, d.extra) for d in deps] == [
        ("openai", None),
        ("openai", "llm"),
        ("httpx", None),
    ]
