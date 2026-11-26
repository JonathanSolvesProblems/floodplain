## openai 3.60.0: none of the 16 working test suites broke

`openai` 3.60.0, published at 2026-11-26 07:10 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

**Read clean (16):** captum, chonkie, code-puppy, echo-agent, evalplus, graphifyy, graphiti-core, highcharts-core, jcodemunch-mcp, krepis, llm, oci-openai, openai-messages-token-helper, openenv-core, shiny, vlmrun.

**Not counted:** chonkie had 1 test fail once after the release (`tests.chunkers.test_code_chunker::test_code_chunker_initialization`) that passed when re-run twice in the same after fork and once in the before fork, so it is a flaky test, not a break.

**Not counted:** echo-agent had 1 test fail once after the release (`tests.test_local_embed::test_cache_dir_passed_to_fastembed`) that passed when re-run twice in the same after fork and once in the before fork, so it is a flaky test, not a break.

**Held back (3):** the release never reached these suites, because another dependency kept openai at an older version: opentelemetry-instrumentation-openai, swebench, vlmrun-hub.

10 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.60.0`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.60.0). [How it works](https://github.com/JonathanSolvesProblems/floodplain).
