## openai 3.40.0: none of the 21 working test suites broke

`openai` 3.40.0, published at 2026-10-27 15:38 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

**Read clean (21):** captum, chatlas, chonkie, code-puppy, dspy, echo-agent, evalplus, foundry-local-sdk, graphifyy, graphiti-core, highcharts-core, jcodemunch-mcp, krepis, langextract, llm, nextcloud-mcp-server, oci-openai, openai-messages-token-helper, openenv-core, shiny, yutori.

**Not counted:** captum had 1 test fail once after the release (`tests.attr.test_feature_ablation.Test::test_future_output_2`) that passed when re-run twice in the same after fork and once in the before fork, so it is a flaky test, not a break.

**Held back (2):** the release never reached these suites, because another dependency kept openai at an older version: opentelemetry-instrumentation-openai, swebench.

7 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.40.0`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.40.0). [How it works](https://github.com/JonathanSolvesProblems/floodplain).
