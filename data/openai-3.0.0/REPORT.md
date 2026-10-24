Posted on 24 October 2026 by `floodplain report` from the committed results of the openai 3.0.0 run. That run was made before the watcher existed, so this is the issue it would have opened.

## openai 3.0.0: 3 of the 20 working test suites broke

`openai` 3.0.0, published at 2026-08-12 01:55 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

### llm 0.32

110 tests broke (it had 1069 passing before).

**Why** (NVIDIA Nemotron 3 Nano, quoting the log): The upstream release switched to HTTPX2 as the default client, altering how HTTP requests are made and breaking test expectations for mocked POST requests.

> `The following responses are mocked but not requested: - Match POST request on https://api.openai.com/v1/chat/completions`

**Patch:** passed the package's own suite in a further fork in 5 of 5 independent runs of the scripted fixer.

```diff
diff --git a/pyproject.toml b/pyproject.toml
index 8ec3191..eaa636e 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -27,7 +27,7 @@ classifiers = [
 dependencies = [
     "click",
     "condense-json>=1.1",
-    "openai>=2.32.0",
+    "openai>=2.32.0,<3.0.0",
     "click-default-group>=1.2.3",
     "sqlite-utils>=4.0",
     "pydantic>=2.0.0",
```

### openinference-instrumentation-agno 1.0.2

6 modules failed to import (it had 92 passing before).

**Why** (NVIDIA Nemotron 3 Nano, quoting the log): The upstream release removed the HTTPTransport attribute from the httpx package, breaking imports that relied on it.

> `AttributeError: module 'httpx' has no attribute 'HTTPTransport'. Did you mean: 'Transport'?`

> `ImportError: cannot import name 'AsyncClient' from 'httpx' (/work/venv/lib/python3.12/site-packages/httpx/__init__.py)`

**Patch:** passed the package's own suite in a further fork in 5 of 5 independent agent runs. This one took 16 steps the agent chose: draft_patch, list_files, read_file, read_file, read_file, read_file, read_file, read_file, read_file, read_file, read_file, read_file, read_file, read_file, ....

```diff
diff --git a/python/instrumentation/openinference-instrumentation-agno/pyproject.toml b/python/instrumentation/openinference-instrumentation-agno/pyproject.toml
index 4b708f2d..7cd6bae1 100644
--- a/python/instrumentation/openinference-instrumentation-agno/pyproject.toml
+++ b/python/instrumentation/openinference-instrumentation-agno/pyproject.toml
@@ -43,7 +43,7 @@ test = [
   "opentelemetry-sdk",
   "pytest-recording",
   "brotli",
-  "openai",
+  "openai<3.0.0",
   "ddgs",
   "yfinance",
   "fastapi",
```

### vlmrun 0.7.3

3 tests broke (it had 231 passing before).

**Why** (NVIDIA Nemotron 3 Nano, quoting the log): The upstream release no longer installs the `httpx` package, causing a ModuleNotFoundError when code imports it.

> `ModuleNotFoundError: No module named 'httpx'`

**Patch:** passed the package's own suite in a further fork in 5 of 5 independent agent runs. This one took 27 steps the agent chose: draft_patch, list_files, read_file, read_file, read_file, search, read_file, read_file, search, run_command, read_file, read_file, read_file, read_file, ....

```diff
diff --git a/requirements/requirements.txt b/requirements/requirements.txt
index 7ea077a..4de4c45 100644
--- a/requirements/requirements.txt
+++ b/requirements/requirements.txt
@@ -1,4 +1,5 @@
 cachetools
+httpx
 IPython
 loguru
 opencv-python>=4.8.0
```

**Read clean (17):** captum, chatlas, code-puppy, echo-agent, evalplus, foundry-local-sdk, graphifyy, highcharts-core, inspect-swe, jcodemunch-mcp, langextract, nextcloud-mcp-server, openai-messages-token-helper, openenv-core, shiny, vanna, yutori.

**Held back (11):** the release never reached these suites, because another dependency kept openai at an older version: chonkie, dspy, graphiti-core, inspect-scout, krepis, lumibot, oci-openai, opentelemetry-instrumentation-openai, swebench, vlmrun-hub, xpander-sdk.

115 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.0.0/experiments`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.0.0/experiments). [How it works](https://github.com/JonathanSolvesProblems/floodplain).

