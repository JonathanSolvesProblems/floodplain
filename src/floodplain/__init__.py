"""Floodplain: run the test suites of everyone who depends on you, before you publish."""

import os

# Credentials pasted through Windows tools can arrive with a byte-order mark or a trailing
# newline. The Sandboxes SDK and the openai client put these values straight into HTTP
# headers, which must be ASCII, so one invisible character fails every request. Clean them
# once, here, before any client reads the environment.
for _name in ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "NEBIUS_AI_PROJECT", "TAVILY_API_KEY", "GITHUB_TOKEN", "GH_TOKEN"):
    _value = os.environ.get(_name)
    if _value is not None:
        _clean = _value.replace("﻿", "").strip()
        if _clean != _value:
            os.environ[_name] = _clean
