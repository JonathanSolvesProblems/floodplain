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
and harness revisions, five runs each. In none of the 30 did it call `submit` or `give_up`. Every
run spent its whole step budget reading files and running tests, including in the final revision,
which handed it a ready patch to start from and, every 12 steps, asked it to name the cause in two
sentences and submit the smallest fix. A single Ultra drafting call, with no tools, fixed the same break in 9 of 10 runs. On the two
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
VIDEO_URL_AFTER_RECORDING
```

## Did the project exist before the submission period

```
No
```
