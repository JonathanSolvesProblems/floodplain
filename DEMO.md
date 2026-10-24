# Demo script

About two minutes; the hackathon limit is three. Every number spoken here is on the live page
or in the repository, read from the committed data. Record against
https://jonathansolvesproblems.github.io/floodplain/ at 1280 wide.

## 1. Simon's nine days (0:00 to 0:15)

> Simon Willison maintains `llm`, a command-line tool for language models. On the twelfth of
> August, openai 3.0.0 came out and swapped its HTTP library. Six hours later a user told him
> fresh installs of `llm` were broken. Nine days later he shipped a pin.

On screen: [llm #1608](https://github.com/simonw/llm/issues/1608), then the
[0.32.1 release](https://github.com/simonw/llm/releases/tag/0.32.1) with its one changed line.

## 2. The question (0:15 to 0:25)

> OpenAI's own tests passed. The break only showed up in other people's test suites. openai
> ships three or four releases a week. So I built something that runs those suites before you
> publish, and fixes what breaks.

On screen: the overview page, the headline and the river.

## 3. Before the release (0:25 to 0:50)

> I gave it OpenAI's own 3.0.0 wheel as an unpublished file, against PyPI as it was a minute
> before the upload. Every package that depended on openai, each run in Nebius Sandboxes as
> three forks of one checkout: before, the same again to catch flaky tests, and after. Of the
> twenty working test suites the release reached, three broke, the same three users hit, down to
> the same tests. Each break is re-run before it is believed.

On screen: the river with its three green stretches; the pre-release sentence under it.

## 4. One break, read (0:50 to 1:05)

> Open `llm`. A thousand and sixty-nine tests passed before. After the release, a hundred and ten
> fail. Nemotron Nano reads the log and says why, quoting the log, and the one line it tried to
> cite that is not in the log was thrown out.

On screen: click `llm`; the three sample columns; the test grid with the 110 in green; the
triage with its quote highlighted in the log.

## 5. The patch (1:05 to 1:20)

> Nemotron writes the patch, and llm's own test suite judges it in a further fork. It is the same
> pin Simon shipped nine days later.

On screen: the diff beside the maintainer's line. Hold three seconds.

## 6. The agent (1:20 to 1:40)

> For agno, the agent takes it from a first draft. Every step here is its own choice: it reads the
> draft, runs the failing tests in a fresh sandbox, revises, and submits. Five runs out of five.

On screen: open openinference-instrumentation-agno; the list of the agent's steps ending in
"VERIFIED".

## 7. It keeps watching (1:40 to 1:55)

> Every day it checks for a new openai release and writes what it found into GitHub. Its first:
> openai 3.37.0. Nothing broke, and the one test that looked broken passed when it was re-run,
> so it says so instead of counting it.

On screen: the GitHub issue the watcher opened for 3.37.0. End on it.

## Recording notes

- Say "a user told him", not that Simon found it: the issue was opened by @aborruso.
- Say "the same pin Simon shipped": four of the first round's five verified patches were that pin.
- Do not say the agent fixed llm. It did not (0 of 25 runs across revisions 3 to 7, 0 of 5 for
  revision 8); the llm patch comes from the drafting call, as in the first rounds.
- Do not say Tavily produced the fix.
