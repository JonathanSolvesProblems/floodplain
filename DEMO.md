# Demo script

Target 90 seconds, hard ceiling 3 minutes (the hackathon limit). Narration locked before
recording. The final shot is a patch, not a number.

## Opening, 0:00 to 0:12

> On the twelfth of August, openai 3.0.0 moved from httpx to httpx2. Simon Willison's `llm`
> is one of thousands of packages that depend on it. His fresh installs broke, and his test
> suite started talking to the live API instead of the mock. It took nine days to find.

On screen: the real GitHub issue, `simonw/llm#1608`, opened 5.9 hours after the release, closed
nine days later.

## The question, 0:12 to 0:22

> Nobody could have known in advance, because the evidence was in other people's repositories
> and other people's test suites. Floodplain goes and runs them.

On screen: type `openai`, pick the `3.0.0` tag, press go.

## The fan-out, 0:22 to 0:40

> It finds every package in the top fifteen thousand that depended on openai on the day of the
> release, and that had no upper bound to protect it. A hundred and fifty-seven of them.

On screen: the grid fills in. Tiles light up as forks complete.

> Each one gets a single checkout, then three forks of that checkpoint on Nebius Sandboxes at
> once. One with the dependency world frozen a minute before the release. One a minute after.
> And a third identical to the first, which is how we know a failure is real and not a flaky
> test.

On screen: one tile expands to show its three forks running in parallel.

## The finding, 0:40 to 1:00

> `llm` passes one thousand and sixty-nine tests before. It passes one thousand and sixty-nine
> again in the control. After the release, a hundred and ten of them fail.

On screen: the three columns, 1069 / 1069 / 959 + 110.

> No test disagreed with itself across the two identical forks, so none of the hundred and ten
> is flaky. Nemotron Nano reads the log and says why: pytest-httpx mocks httpx, openai now uses
> httpx2, the mocks never fire, and the suite goes to the real API.

On screen: the triage card, with its evidence quotes highlighted **in the log**, and the count
of quotes it tried to use that were not in the log, dropped.

## The patch, 1:00 to 1:20

> Nemotron Super drafts a fix, Tavily pulls the upstream's own migration guide, and the patch
> is applied in a fourth fork where that project's own test suite decides whether it worked.

On screen: the diff. Then the suite re-running. Then green.

> Floodplain does not open pull requests against repositories you do not own. It hands you the
> patch.

On screen: the `patches/` directory, one `.patch` file per broken dependent.

## The receipt, 1:20 to 1:30

> Across the hundred and fifty-seven, N broke, M have a patch verified by the project's own
> tests, and K of the breaks were never reported publicly at all.

On screen, for fifteen seconds only: the summary table, then back to the patch file.

---

## Rules this script is checked against

- **Check 1 / rule 87**: the last shot is an artifact the agent made (a patch), not a verdict
  it returned. The grid is a receipt, not the climax.
- **Rule 60**: the name promises a flood plain, and the demo shows the map of what gets hit.
- **Rule 59**: every number on screen is produced by Nemotron or by the dependents' suites, and
  the narration credits exactly what produced it.
- **Rule 73**: the dropped-quote count and the unverified-patch count are both on screen,
  announced by the product about itself.
- **Pre-submit check 9**: the climax is a success (a green suite), not a diagnosis.
