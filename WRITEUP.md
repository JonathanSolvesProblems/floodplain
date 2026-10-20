# Devpost submission fields

## Project name

```
Floodplain
```

## Elevator pitch

```
Test your unreleased package against every project that depends on it, in forked Nebius Sandboxes. Nemotron explains each break and drafts a patch their own test suite has to pass.
```

## About the project

```markdown
## Inspiration

Simon Willison maintains `llm`, a command-line tool for language models. On 12 August 2026, openai 3.0.0 swapped its HTTP library from `httpx` to `httpx2`. Six hours later a user opened [llm #1608](https://github.com/simonw/llm/issues/1608): fresh installs were broken, and the test suite was escaping its mocks to call the live API. Nine days later Simon shipped a pin below 3.

OpenAI's own tests passed. The break only showed up in other people's test suites, so nobody upstream could see it. I wanted a maintainer to be able to run those suites before publishing.

## What it does

Floodplain takes a package and a release (or an unpublished wheel), finds the projects that depend on it among the top 15,000 on PyPI, and runs each one's own test suite in Nebius Sandboxes, three forks of one checkout at a time:

- **before**: the dependency world a minute before the release
- **control**: the same again, so a flaky test is caught instead of blamed on the release
- **after**: a minute after, or the before world with your unpublished wheel offered as the newest version

A test that passes before, fails after, and agrees with itself across the two identical forks was broken by the release. NVIDIA Nemotron 3 Nano then reads the failing log and says why, quoting only lines that really are in it. Nemotron 3 Super and Ultra draft a patch, and the broken project's own test suite judges it in a further fork. Floodplain hands over the patch; it never opens pull requests in other people's repositories.

## What it found on openai 3.0.0

220 of the top 15,000 PyPI packages declared openai on release day. 63 pinned below 3.0.0. Of the other 157, I ran the 146 whose source I could check out. 20 had a working test suite that actually installed 3.0.0, and 3 of them broke:

- `llm`: 110 of 1,069 tests
- `openinference-instrumentation-agno`: all 92, lost to import errors
- `vlmrun`: 3 of 231

Each break was later pinned or patched by its own maintainers, 6, 9 and 19 days after the release.

Then I ran it as OpenAI could have, before publishing: their own 3.0.0 wheel as an unpublished file, against the index a minute before the upload. All 31 dependents with working suites gave the same verdict as the replay of the real release, with the same tests broken.

Nemotron's patches passed the broken project's own suite in 5 of 5 runs for llm (4 of them the exact pin Simon shipped), 5 of 5 for agno and 2 of 5 for vlmrun, in the first round. After I fixed a context bug in my fixer, the second round was 4 of 5, 5 of 5 and 4 of 5. Every figure on the page is read from the committed results, and a script fails the build if the README disagrees with them.

## How I built it

- **Nebius Token Factory Sandboxes** run every fork. Images are content-addressed, so one checkout becomes three identical starting points, and each patch is tested in a further fork of the after image.
- **NVIDIA Nemotron 3** on Token Factory: Nano for triage, Super then Ultra for patches. Every quote in a triage is checked verbatim against the log.
- **Tavily** search and extract for migration guidance, with two guards: only pages dated before that project's maintainers acted, and nothing from or naming the project's own repository. Without them, Tavily's top result was llm's own issue, where the fix is discussed. Every response is committed, so a rerun needs no key.
- **uv** resolves each fork with the index frozen by upload time (`--exclude-newer`), and offers an unpublished wheel through `--find-links` so it resolves exactly as a new release would.
- A static results page (vanilla JavaScript and SVG, on GitHub Pages) drawn as a hydrogeological dye trace: the release is poured in upstream, and each project that broke turns its own stretch of the river green.

## Challenges I ran into

Most of the work was refusing results that looked good. Each of these would have published something untrue:

- A fork that returned nothing was reported as "nothing broke".
- A patch that fixed nothing in a suite that could not even import came back "verified".
- 11 dependents were counted as passing although their after fork never installed 3.0.0, because another package held openai at 2.x. The headline went from 3 of 31 to 3 of 20.
- My first pre-release mode installed the wheel over an already-resolved environment, which kept `httpx` installed and hid exactly the breaks agno and vlmrun had.
- The Sandboxes beta returns intermittent HTTP 500s that the SDK does not retry, so every call is wrapped in a retry with backoff.

## Accomplishments that I'm proud of

The pre-release check reproduced the real release exactly, test for test, from public data and an unpublished file. And the llm patch Nemotron wrote is the same line the maintainer shipped nine days later.

## What I learned

One verified patch is a sample, not a behaviour: I report every fix as K of N runs, per fixer revision, and never pool them. And Nemotron Ultra's patches passed twice as often as Super's (13 of 27 attempts against 12 of 55), so escalating early is worth it.

## What's next

Run it on the next big release before it ships, and offer it as a CI step a maintainer adds to their release workflow.
```

## Built with

```
python, uv, nebius-token-factory, nebius-sandboxes, nvidia-nemotron, tavily, pytest, javascript, svg, github-pages
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
- Every number above is also a tagged claim in README.md; rerun `scripts/check_claims.py` after any data change and re-read this file against it.
