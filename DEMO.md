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
> the failing tests in a fresh sandbox, and decides for itself when the patch is ready to submit.
> It fixed both, five runs out of five. On llm it kept investigating instead of submitting, and the page says so,
> because every fix is reported as runs passed out of runs tried, not one lucky sample. And it
> keeps going. Every day a GitHub Action checks for a new openai release. Its first was 3.37.0,
> where nothing broke and one flaky test was caught and set aside instead of reported. Everything
> lands where maintainers already work: an issue in GitHub, with the evidence and the patches their
> own test suites passed.

## Shots, in order

Each shot is on screen while the words beside it are spoken. Every figure spoken gets its
source as a lower third at that moment; the same sources are listed in the README.

1. Title card: headshot, Floodplain, jonathansolvesproblems.com.
2. "openai 3.0.0 swapped its HTTP library": the
   [openai-python v3.0.0 release notes](https://github.com/openai/openai-python/releases/tag/v3.0.0),
   "HTTPX2 is now the default HTTP client, and httpx is no longer installed automatically".
3. "Six hours later, a user told Simon Willison": [llm #1608](https://github.com/simonw/llm/issues/1608),
   opened by aborruso.
4. "nine days to ship a fix ... other people's test suites": the
   [0.32.1 release](https://github.com/simonw/llm/releases/tag/0.32.1), "pins LLM to use OpenAI
   Python versions less than v3.0.0".
5. "about fifteen releases a month": the [PyPI release history](https://pypi.org/project/openai/#history).
6. "So I built Floodplain": the overview, headline and river, the dye arriving.
7. "three forks of the same checkout ... comparison fair": "How a receptor is read", with the
   one-checkout-three-forks diagram.
8. "146 real packages": "Every receptor I hung", the strip of 146 packets.
9. "Of the 20 working suites ... 3 broke ... re-run before it counts": the river again.
10. "Then I gave it OpenAI's own wheel ... before publishing": the pre-release paragraph under
    the river, "All 31 working suites gave the same verdict as the replay".
11. "Here's llm: 1,069 ... 110": the llm page, the forks line and the test grid.
12. "Nemotron 3 Nano reads the log": "Why it broke", the quote highlighted in the log.
13. "Then Nemotron writes the patch ... the same pin Simon shipped": the diff beside "What the
    maintainer shipped" and its caption "It is the same pin the maintainer shipped."
14. "a Nemotron 3 Ultra agent ... ready to submit": openinference-instrumentation-agno, the
    agent's steps scrolling to the verified submit.
15. "five runs out of five": the agno rounds, "revision 8 ... 5 of 5 runs passed the suite".
16. "On llm it kept investigating": the llm rounds, revisions 3 to 8.
17. "Every day a GitHub Action": "Still watching".
18. "Its first was 3.37.0": [issue #1](https://github.com/JonathanSolvesProblems/floodplain/issues/1),
    with its "Not counted" line.
19. "an issue in GitHub, with the evidence and the patches": [issue #2](https://github.com/JonathanSolvesProblems/floodplain/issues/2),
    scrolling through the three verified diffs. End on it.
20. End card: the headshot again, with the repository and the live page.

## How the video is made

The scripts are in [scripts/video/](scripts/video/) and run from the repository root; the
working files go in `broll/`, which is ignored by git.

1. `transcribe_check.py` transcribes the take (faster-whisper small, word timestamps) so the
   spoken span and every number can be checked against the script above.
2. `capture_site.py` records the site shots frame by frame at a real 1280x720 viewport and 1.5x
   device scale (scroll position and the river's animation set per frame, one screenshot each,
   assembled at 25 fps). `capture_broll.py` records the GitHub and PyPI pages with Playwright's
   video recorder at a 1920x1080 viewport zoomed 1.5x.
3. `make_cards.py` draws the title and end cards in the site's own palette and faces.
4. `build_plan.py` cuts the beats at the words where they start, assigns each its clip and the
   source lower third from `broll/_sources.json`, repairs the caption tokens Whisper mangles,
   and writes `demo.edit-plan.json`; `vidkit assemble` renders it.
5. `fix_audio.py` puts an inaudible floor under every stretch of exact digital silence and
   remuxes once, and `validate_video.py` checks the finished file: length, loudness, black
   frames, silence, AAC packet timing, and one frame per beat.

## Recording notes

- The take of 24 October ran 3:14 at about 124 words a minute, 14 seconds over the limit once
  the cards are counted. The video plays it at 1.12x with the pitch kept, which lands at 2:59.
  Next time, read at about 150 words a minute and the video needs no speed-up.
- Say "a user told him", not that Simon found it: the issue was opened by @aborruso.
- Say "the same pin Simon shipped": four of revision 1's five verified patches were that pin, and
  the page shows one of them.
- Do not say the agent fixed llm. It did not (0 of 30 agent runs across revisions 3 to 8); the
  llm patch comes from the drafting call of the first fixer revision.
- Issue #2 says on its first line that it was posted afterwards from the committed 3.0.0 results;
  do not call it a live watcher run.
- Do not say Tavily produced the fix.
