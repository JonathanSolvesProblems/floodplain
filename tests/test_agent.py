import asyncio
from types import SimpleNamespace

from floodplain.agent import TOOLS, _safe_targets


def test_test_targets_are_relative_paths_or_node_ids_only():
    got = _safe_targets("tests/test_llm.py -k foo tests/x.py::t[a-b] ; rm -rf / ../etc/passwd /abs")
    assert got.split() == ["tests/test_llm.py", "foo", "'tests/x.py::t[a-b]'", "rm"]
    assert "/abs" not in got and ".." not in got and "-rf" not in got


def test_the_agent_can_end_only_through_submit_or_give_up():
    names = {t["function"]["name"] for t in TOOLS}
    assert {"submit", "give_up", "run_tests", "run_command", "edit_file", "read_file", "search", "list_files"} == names
