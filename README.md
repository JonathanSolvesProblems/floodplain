# Floodplain

Run the test suites of the packages that depend on you, against a release you have not shipped yet.

You are about to publish. You know what you changed. You do not know who it breaks, because
that lives in other people's repositories and other people's test suites. Floodplain goes and
runs them.

Work in progress for the Nebius x NVIDIA Global AI Hackathon. This README will be rewritten
before submission.

## How it works

For each package that depends on yours, Floodplain takes one checkout and forks it three ways
in a Nebius Token Factory Sandbox, with the dependency world frozen at a different moment in
each fork:

| fork | dependency world | purpose |
|---|---|---|
| before | one minute before your release | the baseline |
| after | one minute after your release | what your users get |
| control | one minute before, again | the flake check |

A test that passes in `before`, fails in `after`, and agrees with itself in `control` was broken
by your release. A test that disagrees with itself across the two identical forks is flaky, gets
named, and is thrown out rather than counted against you.

NVIDIA Nemotron then reads the failing log and says why, quoting only text that appears in the
log, and drafts a patch. The patch is applied in a further fork and that project's own test
suite decides whether it worked.

## Status

Reproduced on the real thing: `openai` 3.0.0 shipped on 12 August 2026 and moved from `httpx` to
`httpx2`. Against `simonw/llm` 0.32:

| fork | openai | httpx | result |
|---|---|---|---|
| before | 2.54.0 | 0.28.1 | 1,069 passed |
| control | 2.54.0 | 0.28.1 | 1,069 passed, no flakes |
| after | 3.0.0 | not installed | 959 passed, 110 failed, 110 errors |

`pytest-httpx` mocks `httpx`. The new `openai` uses `httpx2`, so the mocks never fire and the
suite goes to the live API instead. Floodplain found that from public package metadata, without
being told the issue existed.

## Licence

MIT.
