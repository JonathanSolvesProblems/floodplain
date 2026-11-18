## openai 3.55.0: none of the 14 working test suites broke

`openai` 3.55.0, published at 2026-11-18 05:22 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

**Read clean (14):** captum, chonkie, code-puppy, graphifyy, graphiti-core, highcharts-core, jcodemunch-mcp, krepis, langextract, llm, oci-openai, openai-messages-token-helper, openenv-core, shiny.

**Not counted:** jcodemunch-mcp had 1 test fail once after the release (`tests.test_fast_path_no_hydration::test_a_fast_path_event_never_hydrates_the_base_index`) that passed when re-run twice in the same after fork and once in the before fork, so it is a flaky test, not a break.

**Held back (5):** the release never reached these suites, because another dependency kept openai at an older version: foundry-local-sdk, nextcloud-mcp-server, opentelemetry-instrumentation-openai, swebench, vlmrun-hub.

11 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.55.0`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.55.0). [How it works](https://github.com/JonathanSolvesProblems/floodplain).
