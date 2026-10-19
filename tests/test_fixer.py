from floodplain.fixer import apply_edits


def test_apply_edits_exact_once():
    files = {"a.py": "import httpx\n\ndef f():\n    return httpx.get\n"}
    out, err = apply_edits(files, [{"path": "a.py", "search": "import httpx\n", "replace": "import httpx2 as httpx\n"}])
    assert err is None and out["a.py"].startswith("import httpx2 as httpx\n")


def test_apply_edits_rejects_ambiguous_search():
    files = {"a.py": "x = 1\nx = 1\n"}
    out, err = apply_edits(files, [{"path": "a.py", "search": "x = 1\n", "replace": "x = 2\n"}])
    assert err and "matches 2 times" in err and out == files


def test_apply_edits_rejects_unknown_file_unless_new():
    files = {"a.py": "pass\n"}
    _, err = apply_edits(files, [{"path": "b.py", "search": "nope", "replace": "x"}])
    assert err and "not provided" in err
    out, err = apply_edits(files, [{"path": "b.py", "search": "", "replace": "new = 1\n"}])
    assert err is None and out["b.py"] == "new = 1\n"


def test_apply_edits_forgives_trailing_whitespace_once():
    files = {"pyproject.toml": 'dependencies = [\n  "click",\n]\n'}
    out, err = apply_edits(files, [{"path": "pyproject.toml", "search": '  "click",\n]\n   ',
                                    "replace": '  "click",\n  "httpx2",\n]\n'}])
    assert err is None and '"httpx2"' in out["pyproject.toml"]
