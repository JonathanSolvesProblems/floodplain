# Devpost submission fields

## Project name

```
Floodplain
```

## Elevator pitch

```
Run before openai 3.0.0 shipped, it finds the 3 packages the release breaks, and Nemotron writes fixes their own test suites pass. Now it watches every openai release on Nebius.
```

## About the project

```markdown
## Inspiration

Simon Willison maintains `llm`, a command-line tool for language models. On 12 August 2026, openai 3.0.0 swapped its HTTP library from `httpx` to `httpx2`. Six hours later a user opened [llm #1608](https://github.com/simonw/llm/issues/1608): fresh installs were broken, and the test suite was escaping its mocks to call the live API. Nine days later Simon shipped a pin below 3.

OpenAI's own tests passed. The break only showed up in other people's test suites, so nobody upstream could see it. openai ships three or four releases a week, so this question comes up for its maintainers about fifteen times a month. I wanted them to be able to answer it before publishing.

## What it does

Point Floodplain at a release, or at a wheel you have not published, and it:

1. finds the projects that depend on it among the top 15,000 on PyPI;
2. runs each one's own test suite in Nebius Sandboxes, three forks of one checkout: the world a minute before the release, the same again to catch flaky tests, and a minute after (or the before world with your unpublished wheel offered as the newest version);
3. re-runs every break, twice more in the same after fork and once in the before fork, and keeps only what reproduces;
4. has NVIDIA Nemotron 3 Nano read the failing log and say why, quoting only lines that really are in it;
5. hands each break to a Nemotron 3 Ultra agent that drafts a patch, then decides step by step what to do with it: read code, run a shell command or chosen tests in a fresh fork, revise, redraft, or submit. A patch counts only when the broken project's whole suite passes it in a further fork;
6. writes the report into GitHub: an issue for each new release, or a comment on the release pull request.

A daily GitHub Actions job runs it on every new openai release and keeps going between visits. It never opens pull requests in other people's repositories; it hands over the patch.

## What it found on openai 3.0.0

Run before the release, with OpenAI's own 3.0.0 wheel as an unpublished file against the index a minute before the upload, it found the three packages the release broke, and all 31 dependents with working suites gave the same verdict as a replay of the real release, with the same tests broken:

- `llm`: 110 of 1,069 tests
- `openinference-instrumentation-agno`: all 92, lost to import errors
- `vlmrun`: 3 of 231

Each one was later pinned or patched by its own maintainers, 6, 9 and 19 days after the release. Nemotron's llm patch is the same pin Simon shipped nine days later. The final agent fixed agno and vlmrun in 5 of 5 runs each.

Its first real watch was openai 3.37.0, two days old: none of the working suites broke. One test looked broken, re-ran clean twice in the same fork, and the report says so instead of counting it.

## How I built it

- **Nebius Token Factory Sandboxes** run every fork. Images are content-addressed, so one checkout becomes three identical starting points, and every test run, shell command and patch the agent tries happens in a further fork.
- **NVIDIA Nemotron 3 on Token Factory**, all three tiers: Nano for triage, Ultra for the drafting call and the agent, through native tool calling. Earlier fixer revisions used Super and Ultra.
- **Tavily** search and extract for migration guidance, with two guards: only pages dated before that project's maintainers acted, and nothing from or naming the project's own repository. Without them, Tavily's top result was llm's own issue, where the fix is discussed. Every response is committed, so a rerun needs no key.
- **uv** resolves each fork with the index frozen by upload time, and offers an unpublished wheel through `--find-links` so it resolves exactly as a new release would.
- **GitHub**: the `floodplain` command posts through the GitHub CLI; a scheduled workflow is the watcher.
- A static results page (vanilla JavaScript and SVG, on GitHub Pages) drawn as a hydrogeological dye trace: the release is poured in upstream, and each project that broke turns its own stretch of the river green.

## Challenges I ran into

Most of the work was refusing results that looked good: a fork that returned nothing reported as "nothing broke"; a patch that fixed nothing in a suite that could not import, reported "verified"; 11 dependents counted as passing although 3.0.0 never reached them (the headline went from 3 of 31 to 3 of 20); a first pre-release mode that hid two of the three breaks; and a flaky test on 3.37.0 that would have been my first published "break".

The agent took eight revisions, every one measured on five runs per package and kept. As an open-ended investigator, Nemotron explored llm's 3,000-line plugin for 40 steps and never submitted; given a first draft to work from, it fixed agno and vlmrun every time. On llm the final agent still does not, where a single drafting call fixed it 9 times in 10, and the page says so.

## Accomplishments that I'm proud of

The pre-release check reproduced the real release exactly, test for test, from public data and an unpublished file. Nemotron wrote the same line the llm maintainer shipped nine days later. And every figure on the page and in the README is checked against the committed results by a script that fails the build when they disagree.

## What I learned

Nemotron is an excellent patch writer and a poor judge of when to stop investigating. One verified patch is a sample, not a behaviour, so every fix is reported as K of N runs per fixer revision. And the control fork is not enough on its own: a test can be flaky only after the release.

## What's next

Offer `floodplain check` as a step maintainers add to their release workflow, and run the watcher for more packages than openai.
```

## Built with

```
python, uv, nebius-token-factory, nebius-sandboxes, nvidia-nemotron, tavily, github-actions, pytest, javascript, svg, github-pages
```

## Try it out

```
https://jonathansolvesproblems.github.io/floodplain/
https://github.com/JonathanSolvesProblems/floodplain
```

## Feedback on Nebius and NVIDIA tooling

Paste the contents of FEEDBACK.md.

---

## Notes (not for pasting)

- Track: Coding and Agentic Engineering. Also enter Best Use of Tavily.
- Video link goes in its own field once recorded (script in DEMO.md).
- "Existed before the Submission Period" field: no; the repository was created during it.
- Every number above is also a tagged claim in README.md; rerun `scripts/check_claims.py` after any data change and re-read this file against it.
