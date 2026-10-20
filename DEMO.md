# Demo script

About 90 seconds; the hackathon limit is 3 minutes. Every number spoken here is on the live
page, read from the committed data. Record against
https://jonathansolvesproblems.github.io/floodplain/ at 1280 wide.

## 1. Simon's nine days (0:00 to 0:15)

> Simon Willison maintains `llm`, a command-line tool for language models. On the twelfth of
> August, openai 3.0.0 came out and swapped its HTTP library. Six hours later a user told him
> fresh installs of `llm` were broken. Nine days later he shipped a pin.

On screen: [llm #1608](https://github.com/simonw/llm/issues/1608), then the
[0.32.1 release](https://github.com/simonw/llm/releases/tag/0.32.1) with its one changed line.

## 2. The question (0:15 to 0:25)

> OpenAI's own tests passed. The breakage only showed up in other people's test suites. So I
> built something that runs them, before you publish.

On screen: the overview page, the headline and the river.

## 3. The river (0:25 to 0:45)

> Every package in the top fifteen thousand that depended on openai on release day. A hundred
> and forty-six of them, each run in Nebius Sandboxes as three forks of one checkout: the world a
> minute before the release, the same minute again to catch flaky tests, and a minute after.
> Of the twenty working test suites that actually got 3.0.0, three broke. Each one was later
> pinned or patched by its own maintainers, six, nine and nineteen days afterwards.

On screen: hover along the river; the three green stretches; the sentence under it.

## 4. Before the release (0:45 to 0:55)

> Then I ran it the way it is meant to be used: OpenAI's own 3.0.0 wheel as an unpublished file,
> against the index a minute before they uploaded it. All thirty-one working suites gave the
> same answer, down to the same broken tests.

On screen: the pre-release sentence on the overview. Optional cut-in: the terminal running
`run_experiments.py --candidate` (sped up), from `data/nebius-candidate-run.log`.

## 5. One break, read (0:55 to 1:10)

> Open `llm`. One thousand and sixty-nine tests passed before, and the same again in the
> background fork. After the release, a hundred and ten fail. Nemotron Nano reads the log and
> says why. Its quote is highlighted where it really appears in the log, and the one line it
> tried to cite that is not in the log was thrown out, and the page says so.

On screen: click `llm`; the three sample columns; the test grid with the 110 in green; the
triage with its quotes highlighted in the log.

## 6. The patch (1:10 to 1:30)

> Nemotron Super and Ultra draft a patch, and `llm`'s own test suite judges it in a further
> fork. It is the same pin Simon shipped nine days later. I ran the whole loop five times per
> round, so this is a rate, not a lucky sample.

On screen: scroll to the patch. The diff, then the maintainer's line beside it, then the round
lines underneath (five of five in round 1, four of them the same pin). Hold on the diff for the
last three seconds.

> Floodplain does not open pull requests in other people's repositories. It hands you the patch.

## Recording notes

- Say "a user told him", not that Simon found it: the issue was opened by @aborruso.
- Say "the same pin Simon shipped", not "the same patch in every run": four of round 1's five
  were that pin; one was a different, working migration.
- Do not say Tavily produced the fix. Round 1 used OpenAI's own migration guide.
