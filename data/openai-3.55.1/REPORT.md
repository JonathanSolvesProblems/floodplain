## openai 3.55.1: none of the 1 working test suites broke

`openai` 3.55.1, published at 2026-11-18 16:05 UTC. Each dependent ran its own test suite in three forks of one checkout on Nebius Sandboxes: the world a minute before, the same again to catch flaky tests, and a minute after.

**Read clean (1):** vlmrun.

**Held back (2):** the release never reached these suites, because another dependency kept openai at an older version: swebench, xpander-sdk.

26 more could not be read (no tests shipped, nothing passing before, or the run did not finish).

---
Floodplain does not open pull requests in other people's repositories; it hands over the patch. Every figure here is read from the run's results in [`data/openai-3.55.1`](https://github.com/JonathanSolvesProblems/floodplain/tree/master/data/openai-3.55.1). [How it works](https://github.com/JonathanSolvesProblems/floodplain).
