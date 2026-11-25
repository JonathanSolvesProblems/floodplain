## openai 3.59.0: 1 of the 16 working test suites broke

`openai` 3.59.0, published at 2026-11-24 19:19 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

### graphiti-core 0.32.1

1 tests broke (it had 1119 passing before).

**Why** (NVIDIA Nemotron 3 Nano, quoting the log): The test suite fails because Redis and Neo4j services are unavailable, causing connection refusals.

> `redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.`

> `Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 111] Connect call failed ('127.0.0.1', 7687))`

**Patch:** passed the package's own suite in a further fork in 3 of 3 independent agent runs. This one took 26 steps the agent chose: draft_patch, list_files, read_file, search, read_file, read_file, read_file, read_file, read_file, search, read_file, read_file, read_file, run_command, ....

```diff
diff --git a/tests/llm_client/test_openai_generic_client.py b/tests/llm_client/test_openai_generic_client.py
index 3355f25..95445c2 100644
--- a/tests/llm_client/test_openai_generic_client.py
+++ b/tests/llm_client/test_openai_generic_client.py
@@ -112,7 +112,13 @@ async def test_no_response_model_uses_json_object_without_injection():
 async def test_rate_limit_error_is_translated():
     rate_limit = openai.RateLimitError(
         message='slow down',
-        response=SimpleNamespace(status_code=429, headers={}, request=None),
+        response=SimpleNamespace(
+            status_code=429,
+            headers={},
+            request=SimpleNamespace(headers={}),
+            history=None,
+            next_request=None,
+        ),
         body=None,
     )
     client, _ = _make_client(error=rate_limit)
```

**Read clean (15):** captum, chonkie, code-puppy, echo-agent, evalplus, graphifyy, highcharts-core, jcodemunch-mcp, krepis, langextract, llm, oci-openai, openai-messages-token-helper, openenv-core, shiny.

**Not counted:** graphifyy had 1 test fail once after the release (`tests.test_language_override_lifecycle::test_watch_config_changes_keep_semantic_work_visible[False]`) that passed when re-run twice in the same after fork and once in the before fork, so it is a flaky test, not a break.

**Held back (4):** the release never reached these suites, because another dependency kept openai at an older version: opentelemetry-instrumentation-openai, swebench, vlmrun-hub, vlmrun.

9 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.59.0`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.59.0). [How it works](https://github.com/JonathanSolvesProblems/floodplain).
