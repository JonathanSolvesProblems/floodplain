import importlib
import os

import floodplain


def test_credentials_lose_a_byte_order_mark_and_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "﻿key-123\n")
    monkeypatch.setenv("TAVILY_API_KEY", "  tvly-abc ")
    importlib.reload(floodplain)
    assert os.environ["NEBIUS_API_KEY"] == "key-123"
    assert os.environ["TAVILY_API_KEY"] == "tvly-abc"
    os.environ["NEBIUS_API_KEY"].encode("ascii")
