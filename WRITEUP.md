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

On 12 August 2026, openai 3.0.0 swapped its HTTP library from `httpx` to `httpx2`. Six hours later a user opened [llm #1608](https://github.com/simonw/llm/issues/1608) on Simon Willison's `llm`, a command-line tool for language models: fresh installs were broken, and its test suite was escaping its mocks to call the live API. Nine days later Simon shipped a pin below 3.

OpenAI's own tests had passed. The break only showed up in other people's test suites, so nobody upstream could see it coming. openai published 48 releases in the ten weeks after 3.0.0, so its maintainers face this question more than fifteen times a month: which of the packages that depend on us does this release break? I built Floodplain so they can answer it before they publish.

**Run before openai 3.0.0 shipped, Floodplain finds the same 3 packages the real release broke, down to the same tests, and Nemotron writes the one-line fix the llm maintainer shipped nine days later.**

Demo (3 min): https://www.youtube.com/watch?v=EZ6w-OhZga4

## What it does

Point Floodplain at a release, or at a wheel you have not published yet, and it:

1. finds the projects that depend on it among the top 15,000 on PyPI;
2. runs each one's own test suite on Nebius Token Factory Sandboxes, in three forks of one checkout: the world a minute before the release, the same again to catch flaky tests, and a minute after (or, for an unpublished wheel, the before world with the wheel offered as the newest version);
3. re-runs every break twice more in the after fork and once in the before fork, and keeps only what reproduces ([`confirm_break`](https://github.com/JonathanSolvesProblems/floodplain/blob/master/src/floodplain/sandbox.py));
4. has NVIDIA Nemotron 3 Nano read the failing log and say why; any quote that is not word for word in the log is dropped before anything is shown ([`triage.py`](https://github.com/JonathanSolvesProblems/floodplain/blob/master/src/floodplain/triage.py));
5. hands each break to a Nemotron 3 Ultra agent ([`agent.py`](https://github.com/JonathanSolvesProblems/floodplain/blob/master/src/floodplain/agent.py)). It starts from a drafted patch, then chooses every step itself from what the last one returned: read or search the code, run chosen tests or a shell command in a fresh fork, edit, ask for a new draft, submit, or give up. A patch counts only when the broken project's whole suite passes it in a further fork; what the model says about its own patch never counts;
6. writes the result into GitHub, where maintainers already work: an issue for each new release, or a comment on the release pull request. It never opens pull requests in other people's repositories; it hands over the patch.

It keeps going on its own. A daily GitHub Actions job checks PyPI for openai releases it has not seen, runs them, and opens the issue. Its first was openai 3.37.0, two days old: [issue #1](https://github.com/JonathanSolvesProblems/floodplain/issues/1) reports that none of the 21 working suites broke, and that one test which failed once, then passed twice on re-run, is a flaky test, not a break. Its second came on its own schedule, the morning after openai 3.39.0 shipped: [issue #3](https://github.com/JonathanSolvesProblems/floodplain/issues/3), again none of 21.

## What it found on openai 3.0.0

![The openai 3.0.0 trace: the release poured in upstream, and the three dependents it broke dyed green](https://jonathansolvesproblems.github.io/floodplain/og.png)

I gave it OpenAI's own 3.0.0 wheel as an unpublished file, against PyPI as it stood a minute before the upload. All 31 dependents with working suites gave the same verdict as a replay of the real release, with the same tests broken. Three broke:

- `llm`: 110 of its 1,069 passing tests
- `openinference-instrumentation-agno`: all 92, lost to import errors
- `vlmrun`: 3 of 231

Each was later pinned or patched by its own maintainers, 6, 9 and 19 days after the release. Nemotron's verified llm patch is the same pin Simon shipped nine days later, and the final agent fixed agno and vlmrun in 5 of 5 runs each. The full report, with all three patches, is [issue #2](https://github.com/JonathanSolvesProblems/floodplain/issues/2), and every break, log and patch is on the [results page](https://jonathansolvesproblems.github.io/floodplain/).

## How I built it

- **Nebius Token Factory Sandboxes** run every fork, about 1,000 sandbox runs over 146 real packages. Images are content-addressed, so one checkout becomes three identical starting points, and every test run, shell command and patch the agent tries happens in a further fork. The pre-release check uploads the unpublished wheel into a fork with `files=`.
- **NVIDIA Nemotron 3 on Token Factory**, all three tiers behind one OpenAI-compatible API: Nano for triage, Ultra for the drafting call and the agent through native tool calling, and Super in the earlier fixer revisions.
- **Tavily** search and extract, called at runtime for each break, for the upstream's migration guidance. Two guards stop it handing Nemotron the answer: only pages dated before that project's maintainers acted, and nothing from or naming the project's own repository. Without them, Tavily's top result for llm was llm's own issue, where the fix is discussed. Responses are cached in the repo, so a rerun of these results needs no key.
- **uv** resolves each fork with the index frozen at the release's upload time, and offers an unpublished wheel through `--find-links`, so it resolves exactly as a new release would.
- **GitHub**: the `floodplain` command posts through the GitHub CLI, and a scheduled workflow is the watcher.
- A static results page (vanilla JavaScript and SVG, on GitHub Pages) drawn as a hydrogeological dye trace: the release is poured in upstream, and each project it broke turns its own stretch of the river green.

## Challenges I ran into

Most of the work was refusing results that looked good: a fork that returned nothing, reported as "nothing broke"; a patch that fixed nothing in a suite that could not import, reported "verified"; 11 dependents counted as passing although 3.0.0 never reached them, which took the headline from 3 of 31 to 3 of 20; a first pre-release mode that hid two of the three breaks; and a flaky test on 3.37.0 that would have been my first published "break".

The agent took eight revisions, each measured on five runs per package, all kept in the repository. As an open-ended investigator, Nemotron explored llm's 3,000-line plugin until its step budget ran out and never submitted. Given a first draft to work from, it fixed agno and vlmrun every time. On llm the final agent, given the migration guidance, still does not, where the scripted fixer, writing whole patches with Super and escalating to Ultra, fixed it in 9 of 10 runs. With the guidance withheld (an ablation run after submission) it fixed llm in 2 of 5, and the page reports every round as measured.

## Accomplishments that I'm proud of

The pre-release check reproduced the real release exactly, test for test, from public data and an unpublished file. Nemotron wrote the same line the llm maintainer shipped nine days later. And every figure on the page and in the README is checked against the committed results by a script that fails the build when they disagree.

## What I learned

Nemotron is an excellent patch writer and a poor judge of when to stop investigating. One verified patch is a sample, not a behaviour, so every fix is reported as runs passed out of runs tried, per fixer revision. And the flaky-test control fork is not enough on its own: a test can turn flaky only after the release, which is why every break is re-run before it counts.

## What's next for Floodplain

Offer `floodplain check` as a step maintainers add to their release workflow, so the report lands on the release pull request before anything is published, and run the watcher for more packages than openai.

More detail: [write-up](https://jonathanandrei.com/blog/floodplain-pre-release-dependent-tests-nebius-nemotron/) and [code](https://github.com/JonathanSolvesProblems/floodplain).
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

````markdown
# Feedback on Nebius Token Factory, Sandboxes, and NVIDIA Nemotron

Written while building Floodplain, which runs the test suites of a package's downstream
dependents in forked sandboxes. Every item below is something I hit, with the reproduction,
rather than a general impression. Dates are October 2026.

## What I used

| Product | What for |
|---|---|
| Token Factory inference | Nemotron 3 Nano triages a failing test log; Ultra drafts the patch and drives the fixer agent through native tool calling; Super and Ultra wrote the patches in the first two fixer revisions |
| Token Factory Sandboxes | One checkout per dependent, forked three ways, each running a full `pytest` suite; every test run, shell command and patch the agent tries runs in a further fork |
| Nemotron 3 Nano / Super / Ultra | The three tiers above, chosen per task |

## Onboarding: zero to hello world

Inference was genuinely about five minutes. The OpenAI-compatible base URL meant the existing
`openai` client worked with two changed lines, and `/v1/models` let me resolve model ids by
substring instead of hard-coding them, which I appreciated.

Sandboxes took longer, because it is beta-gated. The flow is: find the request form behind
"Request beta access" on `tokenfactory.nebius.com/sandboxes/about`, submit a project id, wait
for an email. Mine came through the same day, which was better than I feared. Two things would
have saved me an hour:

1. **The docs do not say the feature is gated until you are already failing.** The SDK's first
   call returns a bare `403 Forbidden` on `/v1/inspect/`. `get_token_info()` does show every
   permission as `false`, which is the real diagnosis, but nothing points you at it. A 403 body
   saying "Sandboxes is not enabled for this project, request access at <url>" would turn a
   30-minute detour into a 30-second one.
2. **The in-browser Playground on that same page is simulated** and says so in small text ("All
   responses are simulated - no real API calls happen"). I nearly took a working tutorial there
   as evidence that my access was live. Putting that notice next to the "Request beta access"
   button rather than inside the terminal would help.

The CLI's `contree auth ls` is the best diagnostic you ship. `STATUS: inactive` with the
message "token is valid but sandboxes are disabled on <project> (no 'list' permission)" is
exactly right, and it is what I eventually used to confirm activation. I would surface that
same string from the SDK.

## What needs work

### 1. The SDK does not retry 5xx, and the CLI does

This cost me the most time. During beta I see intermittent `500 Internal Server Error` on
`POST /v1/instances` and on the `GET /v1/operations/{uuid}` status poll. One run had all three
of its parallel forks fail this way inside 137 seconds.

Your CLI already handles this. Running `contree images` prints:

```
[WARNING] server answered 500, retrying in 0.1s...
```

The Python SDK does not, so the same transient surfaces as an `ApiStatusCodeError` out of
`_wait_operation` and kills the run. I added my own retry wrapper around every call (5xx, 429
and transport errors, exponential backoff with jitter, never on 4xx). Retrying is safe in this
API precisely because images are immutable and content-addressed, which is a nice property, so
I think the SDK could do this by default. A `retry=` knob on `ContreeConfig` would be enough.

### 2. `images.use()` returns a coroutine on the async client even when it makes no API call

The docs describe `images.use()` as creating an image object without an API call, which reads
as synchronous, and some snippets use it unawaited. On `Contree` (async) it returns a
coroutine, so `sdk.images.use(tag).run(...)` fails with `'coroutine' object has no attribute
'run'` and a `RuntimeWarning: coroutine was never awaited`. Easy to fix once you see it, but
the error does not point at the cause. Either make it genuinely sync on both clients or show it
awaited everywhere in the docs.

### 3. OCI import from Docker Hub returns 500

`sdk.images.oci("python:3.12-slim-bookworm")` fails during the import operation with a 500 on
the status poll. The preloaded catalogue saved me: `contree images` lists several thousand
images and `python:3.12-slim` is there, so `images.use()` on a preloaded tag works perfectly
and is faster anyway. Worth saying in the Sandboxes quickstart that the preloaded catalogue is
the happy path and `images.oci()` is for images you actually cannot find there.

### 4. The project-id environment variable has two names

`docs.tokenfactory.nebius.com/sandboxes/start/set-up-access` has a table showing the CLI reads
`NEBIUS_AI_PROJECT` while the Python SDK and REST read `NEBIUS_PROJECT_ID`. The table is
correct and I am glad it exists, but having both names means `contree auth ls` can report `ok`
while the SDK still fails, or the reverse. One name, or accepting both in both places, would
remove a whole class of confusion.

### 5. Nemotron returns empty `content` when `max_tokens` is small

This is the one most likely to bite other people quietly. Nemotron 3 models emit a reasoning
trace in a separate field (`reasoning` on Nano, `reasoning_content` on Super) and spend
completion tokens on it before producing any `content`. A trivial prompt spent about 50 tokens
reasoning. So:

```python
# returns content='' with finish_reason='length'
await client.chat.completions.create(model=NANO, messages=[...], max_tokens=64)
```

There is no error. You get an empty string. In a pipeline that classifies a few hundred logs,
that is a silent failure that looks like the model declining to answer. I now budget reasoning
headroom and retry once on `finish_reason == "length"` with a larger budget.

Two things would help: note the reasoning-token behaviour in the model card on the catalogue
page, and have the Nano response include `completion_tokens_details.reasoning_tokens` the way
Super already does, so the cost is visible in the usage object on both.

The scale of it, from the first two fixer revisions (86 Super and Ultra calls across 30 fix trials): 541,660 of
566,013 completion tokens were reasoning, 95.7%. At a 14,000-token budget, 4 of Ultra's first 12
replies were still cut off mid-JSON, so the reasoning ate the whole budget before the answer
started. One reply came back with empty `content` even with that headroom. A way to cap
reasoning separately from the answer (a `reasoning_budget`, or `max_completion_tokens` that
excludes reasoning) would make the budget predictable.

### 6. Nemotron 3 Ultra as a tool-calling agent investigates and does not stop

Native tool calling worked first time through the OpenAI-compatible API, with nine tools (list
files, read, search, edit, run chosen tests in a sandbox fork, run a shell command, redraft,
submit, give up). The problem is deciding when it is done.

On `llm`, a 3,000-line plugin broken by openai 3.0.0, I ran the agent 30 times across six prompt
and harness revisions, five runs each. In none of the 30, given the migration guidance, did it call `submit` or `give_up`. Every
run spent its whole step budget reading files and running tests, including in the final revision,
which handed it a ready patch to start from and, every 12 steps, asked it to name the cause in two
sentences and submit the smallest fix. With the guidance withheld (the ablation: five further runs of the final revision) it submitted twice and both patches passed, each passing an explicit `httpx` client to the SDK; five runs cannot separate that from chance. The scripted fixer, writing whole patches with no tools (Super first, then Ultra), fixed the same break in 9 of 10 runs. On the two
smaller breaks the same final agent submitted and passed in 5 of 5 runs each, in about 16 and 29
steps per run.

What would help: guidance in the model card on getting Nemotron 3 to commit in a tool loop (a
recommended system prompt pattern, or whether forcing a named tool through `tool_choice` is
supported on Token Factory), and a note on how the reasoning budget interacts with long tool
histories. Every run is committed in the repository, with each step the agent took.

### 7. A Token Factory outage the status page did not show

On 24 October, for about an hour, `api.tokenfactory.nebius.com` answered every request with an
nginx `503 Service Temporarily Unavailable`, including `GET /v1/models` with no key at all, so it
was not my account. All three Nemotron tiers failed the same way. At the same time
status.nebius.com read "All Systems Operational" with Token Factory green in every region, and
Sandboxes kept working throughout. Two small things would help: report the inference edge on the
status page, and return a JSON error body with a retry hint instead of the bare nginx page, so a
client can tell an outage from a bad request. I now retry 5xx with backoff for up to five
minutes and record a trial that still fails as failed rather than dropping it.

### 8. Per-run `cost` during the free beta

Each run result carries a `cost` field, and my `llm` experiment reported about 2.67 across its
forks. The Sandboxes page says runs do not consume credits during beta, so I assume this is an
informational figure rather than a charge, but I could not confirm that from the API or the
billing page. Saying so in the limits page would let people plan a large fan-out without
hedging.

## What worked well

- **Branching is the right primitive and it is fast.** Three forks of one checkpoint completed
  in 1.6 seconds, each seeing the parent's filesystem and none seeing a sibling's. My whole
  design depends on that isolation being exact, and it was. On a local Docker stand-in I built
  for development, the same three forks took longer and Docker Desktop fell over at
  concurrency, returning 500 on its own ping. The microVMs did not.
- **Content-addressed images** make the experiment reproducible in a way I did not have to
  engineer. The clone is one checkpoint, and the forks are genuinely the same starting state,
  which is the difference between "my A/B is fair" and "I hope my A/B is fair".
- **The preloaded image catalogue** is larger than I expected and removed an import step.
- **Model tiering is real, and the numbers favour escalating early.** Nano is fast and good
  enough to classify a test failure by cause. For patches, measured over 82 attempts across 30
  trials, each judged by the dependent's own test suite: Ultra's patches passed 13 of 27 times
  (48%), Super's 12 of 55 (22%), and 21 of Super's edits could not be applied at all because the
  text it meant to replace was not in the file. My plan tries Super twice before Ultra; the data
  says start with Ultra for anything that has to apply exactly. Being able to move between
  tiers with one string, on one API key, is what made that measurable.
- **The fork primitive made a pre-release check possible.** I uploaded an unpublished wheel
  with `files=` (binary, first try) and offered it to the resolver inside a fork of the
  "before" world. Against openai 3.0.0's own wheel, all 31 dependents with working suites gave
  the same verdict as the replay of the real release, with the same tests broken. That only
  works because every fork starts from exactly the same image.
- **`/v1/models`** returning the catalogue means I resolve model ids at startup by substring
  instead of pinning them, so the project does not rot when a deployment is renamed.

## Would I build on it again

Yes, for this kind of workload specifically. The combination I care about is cheap fan-out of
untrusted code execution with exact state isolation, next to an OpenAI-compatible inference
endpoint on the same key. That is two products I would otherwise be stitching together from
two vendors.

The honest caveat is that the Sandboxes 500s made a 157-way fan-out feel risky until I wrapped
every call in retries. If the SDK retried by default I would have no reservation.
````

## Which model(s) did you use, and why did you choose that size/variant?

```
Three Nemotron 3 tiers on Nebius Token Factory, each where its size pays off.

Nemotron 3 Nano (30B-A3B) triages every break: it reads a failing pytest log and says why, quoting the lines it relies on. That runs once per broken dependent across 146 packages, so it needs to be fast and cheap, and the job is reading, not writing code. Every quote is checked word for word against the real log, so a small model is safe here.

Nemotron 3 Ultra (550B-A55B) writes the patches and drives the fixer agent through native tool calling. I started with Super (120B-A12B) and escalated to Ultra, then measured both on the same breaks: across 82 patch attempts judged by each project's own test suite, Ultra's passed 13 of 27 (48%) and Super's 12 of 55 (22%), and 21 of Super's edits could not even be applied because the text it meant to replace was not in the file. A patch has to apply exactly, so the final fixer uses Ultra throughout.
```

## How would you rate Nemotron's output quality for your use case? (1 = Poor, 10 = Excellent)

```
7 out of 10.

What worked: as a patch writer it is excellent. Given the failing log, the dependency files and the code around the failing symbol, the scripted fixer (two Super attempts, then Ultra) fixed llm in 9 of 10 runs, and four of those patches were the exact pin llm's maintainer shipped nine days after the release. With a first draft to work from, the agent fixed the other two breaks in 5 of 5 runs each, in 8 to 35 steps. Nano's triage was accurate and grounded; when it tried to cite a line that was not in the log, the check caught it. Native tool calls were well-formed throughout.

What fell short: knowing when to stop. As an open-ended investigator of a large codebase (llm's 3,000-line plugin), the agent, given the migration guidance, never submitted in 30 runs across six revisions; it kept reading files and running tests until the step budget ran out, even when handed a working draft and asked every 12 steps to submit. With the guidance withheld it submitted in 2 of 5 runs and both patches passed, which five runs cannot separate from chance. Reasoning also takes most of the budget: 95.7% of completion tokens were reasoning, and a small max_tokens returns empty content with no error.
```

## Did you fine-tune, prompt-engineer, or use Nemotron out of the box? What was your approach?

```
Out of the box, no fine-tuning, with prompt and harness engineering measured on real breaks.

Every model output is checked by something outside the model: Nano's quotes against the log, and every patch by the broken project's own full test suite in a fresh Nebius Sandboxes fork. What the model says about its own patch never counts.

The fixer went through eight revisions, each measured on five independent runs per package and all kept in the repository. Revisions 1 and 2 were a fixed sequence (context, draft, apply, verify, escalate Super to Ultra). From revision 3 Ultra is an agent with nine tools (list, read, search, edit, run chosen tests in a sandbox, run a shell command, redraft, submit, give up). The harness changes were driven by the failures: a larger step budget, a repeat guard, history compaction, a checkpoint every 12 steps, and in revision 8 a first draft written before the loop starts so the agent decides what to do with a concrete patch. That change took agno from 1 of 5 to 5 of 5. Tavily search, with date and repository guards, supplies migration guidance without leaking the maintainers' fix.
```

## How did Nemotron's performance compare to other models you've used for similar tasks?

```
I did not run another vendor's model on these breaks, so the comparisons I can stand behind are the ones I measured inside Nemotron 3, all judged by each project's own test suite.

Across tiers: Ultra's patches passed 13 of 27 times, Super's 12 of 55, and 21 of Super's edits could not be applied at all. For anything that has to apply exactly, start with Ultra.

Across ways of using the same model: writing whole patches from the right context (Super first, then Ultra), the scripted fixer fixed llm in 9 of 10 runs, while Ultra as an open-ended agent fixed it in 0 of 30 with the migration guidance and 2 of 5 without it. Given a first draft, the agent fixed the two smaller breaks in 5 of 5 runs each. So Nemotron compares best as a patch writer and worst as an investigator that has to decide on its own when it is done.
```

## Which Nebius platform capabilities were most valuable to your project and how?

```
Token Factory Sandboxes was the core of the project. Every dependent's test suite runs in three forks of one checkout: the world a minute before the release, the same again as a flaky-test control, and a minute after. Images are content-addressed, so the three forks start from exactly the same state, which is what makes the comparison fair; three forks of one checkpoint came up in 1.6 seconds. Every agent test run, shell command and candidate patch runs in a further fork, and the pre-release check uploads an unpublished wheel with files= and offers it to the resolver inside a fork. In all, about 1,000 sandbox runs over 146 real packages, at up to a 157-way fan-out. A local Docker stand-in fell over at that concurrency; the microVMs did not.

Token Factory inference served all three Nemotron 3 tiers behind one OpenAI-compatible API on the same key as Sandboxes: no GPU instances or deployments to manage. The existing openai client worked with two changed lines, native tool calling drove the agent, and /v1/models let me resolve model ids at startup by substring, so moving a task between Nano, Super and Ultra was one string.
```

## How likely are you to recommend running Nemotron on Nebius to other developers? (1 = Unlikely, 10 = Highly Likely)

```
8 out of 10.

For this kind of workload, fanning out untrusted code in exactly isolated forks next to an inference endpoint on the same key, I know of nothing simpler. It replaced what would otherwise be two vendors stitched together, and the fork primitive is what made the pre-release check possible at all.

What keeps it from higher: the Python SDK does not retry transient 500s (the CLI does), so a large fan-out needed my own retry wrapper; on 24 October Token Factory inference returned 503 for about an hour while the status page showed green; and Sandboxes is beta-gated with a bare 403 until access is granted. All of it is written up with reproductions in my feedback.
```

## How would you rate your experience running Nemotron inference on Nebius compared to previous cloud or local development environments? (1 = Poor, 10 = Excellent)

```
8 out of 10.

Zero to a first Nemotron completion took about five minutes: OpenAI-compatible base URL, one key, model ids resolved from /v1/models. Running Nano, Super and Ultra side by side and measuring them on the same task needed no deployment work at all, which a self-hosted setup could not match at 550B. Compared with my local Docker stand-in for the sandbox side, the forks were faster and stayed up at concurrency.

The deductions are reliability and observability: the unreported 503 outage, a bare nginx error page instead of a JSON body with a retry hint, and no per-request way to cap reasoning tokens separately from the answer.
```

## What additional features or improvements would have made the Nemotron on Nebius experience more effective for your project?

```
1. A reasoning budget separate from the answer budget (a reasoning_budget, or max_completion_tokens that excludes reasoning). 95.7% of my completion tokens were reasoning, and a small max_tokens returns empty content with finish_reason length and no error.
2. Reasoning-token counts in the usage object on Nano, as Super already reports.
3. Default retries in the Sandboxes Python SDK for 5xx, 429 and transport errors, as the CLI already does.
4. The inference edge on the status page, and JSON error bodies with a retry hint instead of a bare nginx 503.
5. A 403 on Sandboxes that says the feature is not enabled and links the access form.
6. Guidance, or tool_choice support, for making Nemotron commit in a tool loop: a recommended system prompt pattern for when to call submit.
7. One environment variable name for the project id across the CLI and the SDK.
```

## What do you most hope to see from the Nemotron team next?

```
A Nemotron tuned to finish agentic work, not only to do it well. Its patches are excellent when it commits to one; the gap I measured is the decision to stop investigating and submit (0 of 30 agent runs on a large codebase with the migration guidance, 2 of 5 without it, against 9 of 10 for the scripted fixer writing whole patches on the same break). Training or guidance aimed at that decision, plus a reasoning budget I can set per request, would make it the default model for this kind of coding agent.
```

## Track

```
Coding and Agentic Engineering
```

## Additional prizes to enter

```
Best Use of Tavily
Most Valuable Feedback
```

## Video demo link

```
https://www.youtube.com/watch?v=EZ6w-OhZga4
```

## Did the project exist before the submission period

```
No
```
