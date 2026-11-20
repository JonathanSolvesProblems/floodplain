## openai 3.57.0: none of the 14 working test suites broke

`openai` 3.57.0, published at 2026-11-20 01:28 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

**Read clean (14):** code-puppy, echo-agent, evalplus, graphifyy, graphiti-core, highcharts-core, jcodemunch-mcp, langextract, llm, oci-openai, openai-messages-token-helper, openenv-core, shiny, vlmrun.

**Held back (3):** the release never reached these suites, because another dependency kept openai at an older version: opentelemetry-instrumentation-openai, swebench, vlmrun-hub.

12 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.57.0`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.57.0). [How it works](https://github.com/JonathanSolvesProblems/floodplain).
