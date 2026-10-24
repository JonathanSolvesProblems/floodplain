# Floodplain

Run the test suites of the packages that depend on yours, against your release, before your
users do. Every suite runs in forked Nebius Sandboxes; NVIDIA Nemotron reads what broke and
drafts a patch that the broken package's own test suite has to pass.

**Results page:** https://jonathansolvesproblems.github.io/floodplain/

![The openai 3.0.0 trace: a river from the release to its dependents, with the three that broke dyed green](site/og.png)

## Why

At 01:55 UTC on 12 August 2026, `openai` 3.0.0 went up on PyPI. It swapped its HTTP client
from `httpx` to `httpx2` and stopped installing `httpx`. Six hours later a user opened
[llm #1608](https://github.com/simonw/llm/issues/1608): fresh installs of Simon Willison's `llm`
were broken and its test suite was escaping its mocks to call the live API. Simon's fix, a pin
below 3, shipped in llm 0.32.1 <!-- claim:fix_hours.llm -->231.3 hours after the release.

OpenAI could not have seen this coming from their own test suite. The evidence lived in other
people's repositories. Floodplain goes and runs them.

## What it found

I took every package in the top 15,000 on PyPI that declared `openai` as a dependency on
release day: <!-- claim:total_dependents -->220. Of those, <!-- claim:protected -->63 pinned
below 3.0.0 and were never exposed. I ran the other <!-- claim:exposed -->157 wherever a source
checkout could be found, <!-- claim:ran -->146 in all, three forks each.

<!-- claim:readable -->20 of them had a test suite that worked before the release and actually
installed 3.0.0 in the after fork. <!-- claim:broken -->3 broke:

| package | what broke | what its maintainers later shipped |
|---|---|---|
| `llm` 0.32 | <!-- claim:broke.llm -->110 of <!-- claim:passed_before.llm -->1,069 passing tests | `openai>=2.32.0,<3` in [0.32.1](https://github.com/simonw/llm/releases/tag/0.32.1), <!-- claim:fix_hours.llm -->231.3 hours later |
| `openinference-instrumentation-agno` | all <!-- claim:broke.openinference-instrumentation-agno -->92 passing tests, lost to import errors | [Arize PR #3574](https://github.com/Arize-ai/openinference/pull/3574), routing the SDK through legacy `httpx`, <!-- claim:fix_hours.openinference-instrumentation-agno -->146.8 hours later |
| `vlmrun` | <!-- claim:broke.vlmrun -->3 of <!-- claim:passed_before.vlmrun -->231, all in `test_gateway.py` | [PR #215](https://github.com/vlm-run/vlmrun-python-sdk/pull/215) pinned `openai==1.109.1`, <!-- claim:fix_hours.vlmrun -->457.9 hours later, without saying why |

The other <!-- claim:status.ok -->17 read clean: every test that passed before still passed
after. A further <!-- claim:status.held-back -->11 had working suites but never received 3.0.0:
their own requirement allowed it, but another package in their tree held openai at 2.x. They
passed, but the release never reached them, so they are not counted either way. Each of the
three breaks was later confirmed by its own maintainers' action, recorded
with links in [maintainer_fixes.json](data/openai-3.0.0/maintainer_fixes.json).

### Before the release, not after

The replay above uses a release that is already on PyPI. The point is to run it before
publishing, so I ran it again as OpenAI could have a minute before they did: their own 3.0.0 wheel (sha256
checked against PyPI) given to Floodplain as an unpublished file, against the index as it stood
at 01:54:48 UTC, one minute before the upload.

All <!-- claim:candidate_run.openai-3.0.0-py3-none-any -->31 dependents with working suites gave
the same verdict as the replay (<!-- claim:candidate_agree.openai-3.0.0-py3-none-any -->31
agree), with the same set of broken tests in
<!-- claim:candidate_same_tests.openai-3.0.0-py3-none-any -->31: the
<!-- claim:candidate_broken.openai-3.0.0-py3-none-any -->3 breaks above, 110 tests for llm, 6
modules for agno and 3 tests for vlmrun, and the same 11 held back. So the check that found
these breaks could have run before anyone hit them.

### The patches

For each break, Nemotron drafted a patch and the package's own suite judged it in a fresh fork.
Nemotron samples differently every run, so one verified patch is a sample, not a behaviour. I
ran the whole fix loop five times per package, in two rounds. Rounds are never pooled, because
the fixer changed between them.

**Round 1**, fixer revision 1, with OpenAI's own migration guide:

| package | verified | what the verified patches did |
|---|---|---|
| `llm` | <!-- claim:fix_k.llm.r1-local-fallback -->5 of <!-- claim:fix_n.llm.r1-local-fallback -->5 | four pinned `openai>=2.32.0,<3.0.0`, the constraint Simon shipped in 0.32.1; one migrated instead, passing an explicit `httpx` client to the SDK so the mocks fire again |
| `openinference-instrumentation-agno` | <!-- claim:fix_k.openinference-instrumentation-agno.r1-local-fallback -->5 of <!-- claim:fix_n.openinference-instrumentation-agno.r1-local-fallback -->5 | an upper pin on `httpx` in the test dependencies |
| `vlmrun` | <!-- claim:fix_k.vlmrun.r1-local-fallback -->2 of <!-- claim:fix_n.vlmrun.r1-local-fallback -->5 | declared `httpx` explicitly, which 3.0.0 no longer brings in |

Two of vlmrun's three failures were my fixer's fault, not the model's diagnosis: it showed
Nemotron only the first 120 lines of each file, vlmrun imports `httpx` further down, and the
edit could not be applied. Revision 2 shows every match with the lines around it, and retries a
failed edit with the file's real text.

**Round 2**, fixer revision 2, with the pages Tavily found:

| package | verified | what the verified patches did |
|---|---|---|
| `llm` | <!-- claim:fix_k.llm.r2-tavily -->4 of <!-- claim:fix_n.llm.r2-tavily -->5 | three migrated, passing an explicit `httpx` client so the mocks fire again; one pinned below 3 |
| `openinference-instrumentation-agno` | <!-- claim:fix_k.openinference-instrumentation-agno.r2-local-fallback -->5 of <!-- claim:fix_n.openinference-instrumentation-agno.r2-local-fallback -->5 | four pinned `openai<3.0.0` in the test dependencies, one pinned `httpx` |
| `vlmrun` | <!-- claim:fix_k.vlmrun.r2-tavily -->4 of <!-- claim:fix_n.vlmrun.r2-tavily -->5 | two pinned `openai` below 3, two declared `httpx` |

For agno, Tavily found nothing dated before Arize's fix that did not name the package, so its
round 2 used OpenAI's guide, and the record says so. Round 2's llm patches lean towards a real
migration rather than a pin, but the fixer revision changed at the same time as the guidance,
so I do not attribute that to either one.

**Rounds 3 to 8: the agent.** Revisions 1 and 2 ran a fixed sequence in code. From revision 3 the
fixer is an agent: Nemotron 3 Ultra chooses every step with tools (described below). Each row is
five independent runs, and every revision is kept, including the ones that did worse:

| revision | what changed | llm | agno | vlmrun |
|---|---|---|---|---|
| 3 | the agent, 24 steps | <!-- claim:fix_k.llm.r3-tavily -->0 of 5 | <!-- claim:fix_k.openinference-instrumentation-agno.r3-local-fallback -->1 of 5 | <!-- claim:fix_k.vlmrun.r3-tavily -->6 of 6 |
| 4 | 40 steps, the budget shown, a shell tool | <!-- claim:fix_k.llm.r4-tavily -->0 of 5 | <!-- claim:fix_k.openinference-instrumentation-agno.r4-local-fallback -->0 of 5 | <!-- claim:fix_k.vlmrun.r4-tavily -->2 of 5 |
| 5 | repeat guard, shorter history, a checkpoint every 12 steps | <!-- claim:fix_k.llm.r5-tavily -->0 of 5 | <!-- claim:fix_k.openinference-instrumentation-agno.r5-local-fallback -->0 of 5 | <!-- claim:fix_k.vlmrun.r5-tavily -->4 of 5 |
| 6 | a drafting tool (never called) | <!-- claim:fix_k.llm.r6-tavily -->0 of 5 | <!-- claim:fix_k.openinference-instrumentation-agno.r6-local-fallback -->3 of 5 | <!-- claim:fix_k.vlmrun.r6-tavily -->3 of 5 |
| 7 | the drafting tool named, shell use capped | <!-- claim:fix_k.llm.r7-tavily -->0 of 5 | <!-- claim:fix_k.openinference-instrumentation-agno.r7-local-fallback -->1 of 5 | not run |
| 8 | a first draft written before the loop; the agent decides what to do with it | <!-- claim:fix_k.llm.r8-tavily -->0 of 5 | <!-- claim:fix_k.openinference-instrumentation-agno.r8-local-fallback -->5 of 5 | <!-- claim:fix_k.vlmrun.r8-tavily -->5 of 5 |

Revision 8 is the one that ships. It fixes agno and vlmrun every time, in 8 to 35 steps:
it reads the draft, runs the failing tests, revises when they say so, and submits. On llm it
never fixes anything. Given a 3,000-line plugin, the agent investigates the openai package
instead of submitting, every time, while the same model writing a whole patch from the right
context, as revisions 1 and 2 did, fixed llm in 9 of 10 runs. That is the clearest thing I learned
about Nemotron here: as a patch writer it is excellent, and as an open-ended investigator of a
large codebase it does not know when to stop.

## How it works

**Three forks of one checkout.** For each dependent, one Nebius Sandbox clones the source at the
released version and persists that image. Three forks start from it at once, each installing
the package and its test dependencies with `uv` and the index frozen at a different moment:

| fork | dependency world | purpose |
|---|---|---|
| before | one minute before the release | the baseline |
| control | one minute before, again | catches flaky tests |
| after | one minute after the release | what a new user got |

A test that passes in `before`, fails in `after`, and agrees with itself between `before` and
`control` was broken by the release. A test that disagrees with itself across the two identical
forks is flaky and is thrown out.

**Pre-release mode.** `--candidate path/to/wheel` replaces the after fork's release with a wheel
you have not published. The wheel is offered to the resolver as the newest version, so a fresh
install gets it with exactly the dependencies it declares, and a package pinned below it keeps
the old version, as it would on release day.

**Triage.** Nemotron 3 Nano reads the failing log and names the cause, with evidence quotes.
Every quote is checked verbatim against the log; one it invented is dropped and counted, not
shown as evidence.

**Fix: an agent that decides its own next step.** One Nemotron 3 Ultra call first drafts a whole
patch from the package's dependency files, the code around the failing symbol and the log. The
agent starts from that draft with the triage, the log and the tools below, and at every step
chooses what to do from what the last tool returned: test the draft, revise it, replace it, or
submit it ([agent.py](src/floodplain/agent.py)):

| tool | what it does |
|---|---|
| `list_files`, `read_file`, `search` | find and read the code and the dependency declarations |
| `edit_file` | a search-and-replace edit on its working copy |
| `run_tests` | any subset of the suite, in a fresh sandbox fork with its edits applied |
| `run_command` | a shell command (pip freeze, python -c) in a disposable fork with its edits applied |
| `draft_patch` | ask the drafting model for a fresh candidate patch, with the agent's notes |
| `submit` | the whole suite in a further fork, judged in code; a rejection comes back with the reasons |
| `give_up` | stop, saying why |

Code enforces only the step budget and the verification gate. A patch counts as verified only if
pytest runs to completion, nothing fails to collect, and every test that passed before the release
passes again, with the full install recipe replayed so a pin in a test extra actually takes
effect. What the agent says about its own patch never counts. Earlier fixer revisions ran a fixed
propose, apply, verify sequence; their trials are kept and reported separately.

**Where it lands.** `floodplain watch` runs every new release of a package against the
dependents that gave a reading last time, lets the agent fix what broke, and opens a GitHub issue
with the report and the verified patches. A daily GitHub Actions job ([watch.yml](.github/workflows/watch.yml))
runs it and commits the results and its state, so it only ever checks releases it has not seen.
Its first report, for openai 3.37.0, is [issue #1](https://github.com/JonathanSolvesProblems/floodplain/issues/1).
`floodplain check --wheel ... --pr N` does the same for an unpublished wheel and posts the report
on the release pull request ([check.yml](.github/workflows/check.yml)). Floodplain never opens
pull requests in other people's repositories; it hands over the patch.

**Research.** Tavily searches for the upstream's migration guidance and extracts the relevant
pages in full. Two guards stop it handing Nemotron the answer: it only sees pages dated before
the day that package's maintainers acted, and any page from the package's own repository, or
naming it, is dropped and recorded. Without them, the top result for openai 3.0.0 was llm's own
issue, where the fix is discussed. Every response is committed under
[data/openai-3.0.0/research/](data/openai-3.0.0/research/), so a rerun replays exactly what the
original run saw and needs no Tavily key.

## The other 126

Most dependents could not give a reading about the release, and the page says why for each one
rather than counting them as passes:

| reading | count | meaning |
|---|---|---|
| held back | <!-- claim:status.held-back -->11 | the suite worked, but another dependency kept openai below 3.0.0, so the release never arrived |
| no baseline | <!-- claim:status.no-baseline -->54 | nothing passed before the release either: the suite needs services, credentials or system packages a sandbox does not have |
| no tests | <!-- claim:status.no-tests -->28 | no test suite ships at the released version |
| incomplete | <!-- claim:status.incomplete -->20 | a fork returned no results (timeout or transport failure) |
| unrunnable | <!-- claim:status.unrunnable -->13 | the package would not install, before or after the release |

## Checks that stopped a false result

Each of these would have published something untrue, and each was caught by a number that did
not add up:

1. A fork that returned nothing was reported as "nothing broke". Now `incomplete`.
2. "Broken" and "ok" verdicts were given against a before fork with zero passing tests. Now
   `no baseline`; [rescore.py](scripts/rescore.py) re-derives every stored verdict when a rule
   changes, without re-running anything.
3. A patch that fixed nothing in a suite that could not import came back "verified": the
   still-failing check skipped collection errors. Caught because pytest exited 2.
4. Verification reinstalled only the base package, so a pin in a test extra never took effect
   and the right agno fix was rejected 20 times out of 20.
5. In a monorepo, the fixer showed the model the repository root, and agno got patches aimed at
   the monorepo's Makefile.
6. Tavily's top result for openai 3.0.0 was llm's own issue, which discusses the fix.
7. The first pre-release mode installed the wheel over an environment already resolved with the
   old release. That kept `httpx` installed, which hid exactly the breaks agno and vlmrun had.
8. 11 dependents were counted as reading clean although their after fork never installed
   3.0.0. A verdict now only counts if the fork resolved the release; otherwise it is
   `held back`. The headline went from 3 of 31 to 3 of 20.
9. The first release the watcher checked, openai 3.37.0, showed echo-agent "broken": one test
   of 6,205, with openai the only package that differed between the forks. The control fork
   cannot catch a test that is flaky only after the release, so every break is now re-run: its
   failing tests twice more in the same after fork and once in the before fork. That one was a
   45-second timeout downloading an embedding model, passed every re-run, and is reported as
   flaky, not as a break.

## Run it

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). Copy `.env.example` to `.env`, or
export the variables: a Nebius Token Factory API key and project id (inference and Sandboxes
both use them), and optionally a Tavily key.

```sh
uv sync --extra dev
uv run python -m pytest                     # unit tests, no keys needed
uv run python scripts/smoke.py              # one fork round trip on Nebius Sandboxes

# the product: watch a package's releases, or check a wheel before you publish it
uv run floodplain watch --target openai --base 3.0.0 --repo OWNER/NAME
uv run floodplain check --target openai --wheel dist/openai-X-py3-none-any.whl --pr 123 --repo OWNER/NAME
uv run floodplain report data/openai-3.0.0/experiments --target openai --release 3.0.0

# the openai 3.0.0 study, step by step

# who depended on the release, and who was exposed to it
uv run python scripts/discover.py   --target openai --release 3.0.0 --scan 15000
uv run python scripts/population.py --target openai --release 3.0.0

# three forks per dependent, then triage and five agent fix trials for each break
uv run python scripts/run_experiments.py --target openai --release 3.0.0 --stage run
uv run python scripts/run_experiments.py --target openai --release 3.0.0 --stage fix --trials 5

# the same check against a wheel you have not published
uv run python scripts/run_experiments.py --target openai --release 3.0.0 --stage run \
  --candidate dist/openai-3.0.0-py3-none-any.whl --as-of 2026-08-12T01:54:48Z

# rebuild the page and confirm every figure in this README against the data
uv run python scripts/stats.py      --target openai --release 3.0.0
uv run python scripts/build_site.py --target openai --release 3.0.0
uv run python scripts/check_claims.py
```

Every figure in this README carries a hidden tag, and `check_claims.py` fails if any of them
disagrees with [stats.json](data/openai-3.0.0/stats.json).

## Built with

- **Nebius Token Factory Sandboxes** for every fork: content-addressed images, so one checkout
  becomes three identical starting points and each patch is tested in a further fork.
- **NVIDIA Nemotron 3** on Token Factory: Nano for triage, Super and Ultra for patches.
- **Tavily** search and extract for migration guidance, behind the guards above.

## Limits

- Only Python packages with a pytest suite that runs without outside services, and that
  actually resolve the release, can give a reading; 20 of 146 did here.
- The replay freezes the index by PyPI upload time, so it reproduces what a fresh install
  resolved on release day, not what any one user's lockfile held.
- One release so far. The method is not specific to openai, but I have only measured it there.

## Sources

Every figure spoken in the demo video, and where it comes from:

- openai 3.0.0 was uploaded to PyPI on 12 August 2026 at 01:55 UTC, with httpx2 as the default
  HTTP client and httpx no longer installed:
  [openai-python v3.0.0](https://github.com/openai/openai-python/releases/tag/v3.0.0),
  [PyPI](https://pypi.org/project/openai/3.0.0/).
- Fresh installs of llm were reported broken 5.9 hours later:
  [simonw/llm #1608](https://github.com/simonw/llm/issues/1608), opened by aborruso on
  12 August 2026 at 07:49 UTC.
- The fix, a pin below 3, shipped 9 days and 15 hours after the upload:
  [llm 0.32.1](https://github.com/simonw/llm/releases/tag/0.32.1), 21 August 2026 at 17:16 UTC.
- openai's release rate: 48 releases on PyPI between 3.0.0 (12 August) and 3.37.0
  (22 October 2026), 20 a month, or 38 minor versions, 16 a month:
  [PyPI release history](https://pypi.org/project/openai/#history). The video says "about
  fifteen a month".
- The 146 dependents run, the 20 working suites the release reached, the 3 that broke, the 31
  of 31 pre-release verdicts matching the replay, llm's 110 of 1,069, and every fix trial by
  revision: [data/openai-3.0.0/stats.json](data/openai-3.0.0/stats.json), built by
  `scripts/stats.py` from the experiment files beside it.
- The first watch, openai 3.37.0, with one flaky test set aside:
  [issue #1](https://github.com/JonathanSolvesProblems/floodplain/issues/1).

## Licence

MIT. Built by Jonathan Andrei for the Nebius x NVIDIA Global AI Hackathon.
