# Feedback on Nebius Token Factory, Sandboxes, and NVIDIA Nemotron

Written while building Floodplain, which runs the test suites of a package's downstream
dependents in forked sandboxes. Every item below is something I hit, with the reproduction,
rather than a general impression. Dates are October 2026.

## What I used

| Product | What for |
|---|---|
| Token Factory inference | Nemotron 3 Nano triages a failing test log; Super drafts the patch; Ultra is the escalation when Super's patch does not pass |
| Token Factory Sandboxes | One checkout per dependent, forked three ways, each running a full `pytest` suite |
| Nemotron 3 Nano / Super / Ultra | The three tiers above, chosen per task cost |

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

The scale of it, from the fix loop (86 Super and Ultra calls across 30 fix trials): 541,660 of
566,013 completion tokens were reasoning, 95.7%. At a 14,000-token budget, 4 of Ultra's first 12
replies were still cut off mid-JSON, so the reasoning ate the whole budget before the answer
started. One reply came back with empty `content` even with that headroom. A way to cap
reasoning separately from the answer (a `reasoning_budget`, or `max_completion_tokens` that
excludes reasoning) would make the budget predictable.

### 6. A Token Factory outage the status page did not show

On 24 October, for about an hour, `api.tokenfactory.nebius.com` answered every request with an
nginx `503 Service Temporarily Unavailable`, including `GET /v1/models` with no key at all, so it
was not my account. All three Nemotron tiers failed the same way. At the same time
status.nebius.com read "All Systems Operational" with Token Factory green in every region, and
Sandboxes kept working throughout. Two small things would help: report the inference edge on the
status page, and return a JSON error body with a retry hint instead of the bare nginx page, so a
client can tell an outage from a bad request. I now retry 5xx with backoff for up to five
minutes and record a trial that still fails as failed rather than dropping it.

### 7. Per-run `cost` during the free beta

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
