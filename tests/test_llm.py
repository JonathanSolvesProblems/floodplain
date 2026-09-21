from downstream.llm import extract_json, verified_quotes


def test_extract_json_plain_and_fenced_and_think():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('here you go:\n```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json('<think>hmm</think>\n{"a": 3}') == {"a": 3}
    assert extract_json('prefix {"a": {"b": 4}} suffix') == {"a": {"b": 4}}


def test_verified_quotes_keeps_only_verbatim():
    log = "E   ModuleNotFoundError: No module named 'httpx'\ntests/test_cli.py:3: in <module>"
    kept, dropped = verified_quotes(
        ["No module named 'httpx'", "ModuleNotFoundError:   No module named 'httpx'", "No module named 'httpx2'"],
        log,
    )
    assert kept == ["No module named 'httpx'", "ModuleNotFoundError:   No module named 'httpx'"]
    assert dropped == ["No module named 'httpx2'"]
