## openai 3.49.0: none of the 18 working test suites broke

`openai` 3.49.0, published at 2026-11-10 06:47 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

**Read clean (18):** captum, chonkie, code-puppy, dspy, echo-agent, evalplus, graphifyy, graphiti-core, highcharts-core, jcodemunch-mcp, krepis, langextract, llm, oci-openai, openai-messages-token-helper, openenv-core, shiny, vlmrun.

**Not counted:** graphifyy had 2 tests fail once after the release (`tests.test_language_override_lifecycle::test_watch_config_changes_keep_semantic_work_visible[True]`, `tests.test_language_override_lifecycle::test_watch_relative_roots_receive_config_events_without_rebasing_source_paths[src]`) that passed when re-run twice in the same after fork and once in the before fork, so it is a flaky test, not a break.

**Held back (3):** the release never reached these suites, because another dependency kept openai at an older version: opentelemetry-instrumentation-openai, swebench, vlmrun-hub.

8 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.49.0`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.49.0). [How it works](https://github.com/JonathanSolvesProblems/floodplain).
