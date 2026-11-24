## openai 3.58.0: none of the 17 working test suites broke

`openai` 3.58.0, published at 2026-11-23 19:02 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

**Read clean (17):** captum, chonkie, code-puppy, echo-agent, evalplus, graphifyy, graphiti-core, highcharts-core, jcodemunch-mcp, krepis, langextract, llm, oci-openai, openai-messages-token-helper, openenv-core, shiny, vlmrun.

**Not counted:** code-puppy had 1 test fail once after the release (`tests.test_session_format_migration.TestJsonRoundTrip::test_list_and_cleanup_handle_both_formats`) that passed when re-run twice in the same after fork and once in the before fork, so it is a flaky test, not a break.

**Held back (3):** the release never reached these suites, because another dependency kept openai at an older version: opentelemetry-instrumentation-openai, swebench, vlmrun-hub.

9 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.58.0`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.58.0). [How it works](https://github.com/JonathanSolvesProblems/floodplain).
