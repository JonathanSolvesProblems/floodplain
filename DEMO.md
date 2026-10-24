# Demo script

About two and a half minutes; the hackathon limit is three. Every number spoken here is on the
live page, in the repository or in the two GitHub issues, read from the committed data. Record
against https://jonathansolvesproblems.github.io/floodplain/ at 1280 wide.

## Narration

> On the twelfth of August, openai 3.0.0 swapped its HTTP library. Six hours later, a user told
> Simon Willison that fresh installs of his tool, llm, were broken, and it took him nine days to
> ship a fix. OpenAI's own tests had passed. The break only showed up in other people's test
> suites, and openai ships about fifteen releases a month. So I built Floodplain. You give it a
> release, or a wheel you haven't published yet, and it runs the test suites of every package that
> depends on it on Nebius Token Factory Sandboxes, each one as three forks of the same checkout: the
> world a minute before the release, the same again to catch flaky tests, and a minute after.
> Because the images are content-addressed, all three start from exactly the same state, which is
> what makes the comparison fair. I ran it on openai 3.0.0 across 146 real packages. Of the 20
> working suites the release actually reached, 3 broke, and every break is re-run before it counts.
> Then I gave it OpenAI's own 3.0.0 wheel as an unpublished file, against PyPI as it was a minute
> before the upload, and it gave the same verdict for all 31 working suites, down to the same
> broken tests, so a maintainer could have seen all of this before publishing. Here's llm: 1,069
> tests passed before, 110 fail after. Nemotron 3 Nano reads the log and says why, and every line it
> quotes is checked against the real log. Then Nemotron writes the patch, and llm's own test suite
> judges it in a further fork. It's the same pin Simon shipped nine days later. For the other two
> breaks, a Nemotron 3 Ultra agent takes over through native tool calling: it reads the code, runs
> the failing tests in fresh sandboxes, revises, and decides when to submit. It fixed both, five
> runs out of five. On llm it kept investigating instead of submitting, and the page says so,
> because every fix is reported as runs passed out of runs tried, not one lucky sample. And it
> keeps going. Every day a GitHub Action checks for a new openai release. Its first was 3.37.0,
> where nothing broke and one flaky test was caught and set aside instead of reported. Everything
> lands where maintainers already work: an issue in GitHub, with the evidence and the patches their
> own test suites passed.

## Shots, in order

1. "On the twelfth of August": [llm #1608](https://github.com/simonw/llm/issues/1608), then the
   [0.32.1 release](https://github.com/simonw/llm/releases/tag/0.32.1) with its one changed line.
2. "So I built Floodplain": the overview page, headline and river.
3. "three forks of the same checkout": scroll the river slowly; the three green stretches.
4. "same verdict for all 31": the pre-release sentence under the river.
5. "Here's llm": click llm; the three sample columns, the test grid with the 110, the triage with
   its quote highlighted in the log.
6. "Then Nemotron writes the patch": the diff beside "What the maintainer shipped". Hold three
   seconds on the caption "It is the same pin the maintainer shipped."
7. "a Nemotron 3 Ultra agent": open openinference-instrumentation-agno; the agent's step list
   ending in a verified submit; the round line "revision 8 ... 5 of 5".
8. "On llm it kept investigating": back on llm, the round lines for revisions 3 to 8.
9. "Every day a GitHub Action": the "Still watching" section, then
   [issue #1](https://github.com/JonathanSolvesProblems/floodplain/issues/1).
10. Final shot, "an issue in GitHub": [issue #2](https://github.com/JonathanSolvesProblems/floodplain/issues/2),
    scrolled to the three verified patches. End on it.

## Recording notes

- Say "a user told him", not that Simon found it: the issue was opened by @aborruso.
- Say "the same pin Simon shipped": four of revision 1's five verified patches were that pin, and
  the page shows one of them.
- Do not say the agent fixed llm. It did not (0 of 30 agent runs across revisions 3 to 8); the
  llm patch comes from the drafting call of the first fixer revision.
- Issue #2 says on its first line that it was posted afterwards from the committed 3.0.0 results;
  do not call it a live watcher run.
- Do not say Tavily produced the fix.
