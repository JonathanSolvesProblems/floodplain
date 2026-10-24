# Phase 0 card

Filled in on 2026-10-24, after the build, when the card became the gate. Every field is
from evidence: the hackathon's own pages (fetched 2026-10-24), the public GitHub trail
while the gallery is unpublished, PyPI, and this repo's committed results.

## 1. Event, odds, currency [rules 16, 29, 75, 79, 92]
- Event, deadline, results date: Nebius x NVIDIA Global AI Hackathon (Devpost). Deadline 2026-10-30 10:00 PDT. Judging 2026-12-01 to 12-15, winners about 2027-01-11.
- Entries (gallery count, or last edition's): gallery unpublished; 26,697 participants on 2026-10-24. 47 public repos match "nebius sandboxes" since the event opened.
- Prizes I am eligible for, and the track I enter (smallest defensible, plus every parallel track): Coding and Agentic Engineering track (one winner, a Jetson Orin Nano), Best Use of Tavily ($3,000), Most Valuable Feedback ($100 x 10), and the overall prizes. No IRL city event attended.
- What the event pays out for (its currency), and proof I can produce it in the window: a working system on Token Factory with an NVIDIA open model, judged on Technological Implementation, Design ("a complete, coherent product experience, not just a technical proof of concept"), Potential Impact, Quality of the Idea. Proof: 146 real dependents run on Nebius Sandboxes, 30 Nemotron fix trials, a live public page.
- Other builds I am running in this window: Watermark (Amazon, submitted 2026-10-22). Nothing else from now to the deadline.
- RED: was RED from 2026-10-13 to 10-22 (field over 1,000 while Watermark ran). Fixed by time: Floodplain is the only build for the remaining six days.

## 2. The winners' verb [check 1, rules 76, 87, 93]
- Three winners of the last comparable event, and what each one's user ended the session HOLDING: no previous edition of this event. Nearest comparable winners: ShipGuard (Google, Individual) holds an Xcode-validated GitHub PR; FlakeWarden (UiPath Test Cloud, 1st) holds a triaged, re-run test failure; Culprit (DataHub) holds a proven root cause written back. The organiser's own bar for this track: "an agent that plans, writes, tests, and iterates on a real repo with minimal human input."
- That in one verb, and the adjectives on its object from the title, subtitle and track text: **write** (and run, and test) code; the object is a working change verified by tests, "in Token Factory."
- What my user ends the session holding: a patch for each dependent the release breaks, written by Nemotron and passed by that project's own test suite in a further sandbox fork, delivered to GitHub.
- RED: no. The breakage detection is the instrument; the patch is the made thing and the final shot.

## 3. A person, and how often [rules 12, 22, 93, 95, 98]
- The person (me, someone I interviewed, or a labelled composite) and the moment the story opens on: Simon Willison (real, public record). 12 August 2026: six hours after openai 3.0.0, a user opens llm #1608, fresh installs broken; nine days later he ships a pin. The user of the tool is the upstream maintainer about to publish; the beneficiary is every downstream maintainer like Simon.
- Times per month they hit this task: openai published 3.0.0 to 3.37.0 in ten weeks (PyPI), about 15 releases a month. Every release is a run.
- RED: no.

## 4. The loop [rule 103]
- "At step X the model chooses between A, B and C, based on what it just observed": after one Nemotron 3 Ultra call drafts a patch, the agent (src/floodplain/agent.py) chooses at every step between reading a file, searching, running a shell command or a chosen subset of tests in a fresh sandbox fork, editing, asking for a fresh draft, submitting for full verification, or giving up, based on the last tool result. A rejected submission returns the judge's reasons and the agent decides what to try next. Code enforces only the step budget, a repeat guard and the verification gate.
- Measured, per revision, 5 runs each (data/openai-3.0.0/stats.json): revision 8 verified agno 5 of 5 and vlmrun 5 of 5 and llm 0 of 5; on llm the agent investigates instead of submitting, where the scripted fixer verified 9 of 10. Stated in the README and on the page.
- RED: was RED (code fixed the sequence). Fixed: the agent loop, revisions 3 to 8, revision 8 ships.

## 5. Where the result lands [rules 4, 27, 33, 101, 103]
- The system the result is written into, which the user already opens (email, ticket, PR, filing, calendar, the sponsor's product): GitHub. `floodplain watch` opens an issue for each new release it checks, with every break, the evidence and the verified patches; `floodplain check --wheel --pr` posts the same report on the release pull request.
- What the agent keeps and does on its own after the first run: data/watch/openai.json records the releases already checked; .github/workflows/watch.yml runs the watcher daily on every new openai release, confirms each break by re-running it, lets the agent fix what still breaks, posts the issue and commits the results. First live run: openai 3.37.0.
- RED: was RED (the page was the only destination). Fixed: watch and check, posting through the GitHub CLI.

## 6. The headline number [check 5, rules 59, 65, 67, 102, 104]
- The number, in world units (seconds, dollars, cases, people): 3 of the 20 working test suites that actually took openai 3.0.0 broke; run before the release, the check gave the same verdict for all 31 working suites, same broken tests; Nemotron's patch passed llm's own suite in 5 of 5 runs, 4 of them the exact pin the maintainer shipped nine days after the release.
- Who grades it, that I did not build and cannot influence: the dependents' own test suites, and what their maintainers later shipped (llm 0.32.1, Arize PR #3574, vlmrun PR #215), recorded in maintainer_fixes.json.
- The sponsor-model call that produces it: the breaks come from Nebius Sandboxes forks; the patches from Nemotron 3 Super and Ultra on Token Factory; the triage from Nemotron 3 Nano.
- Can it be collected (would a busy stranger answer this in one sentence): yes, it is all public: PyPI, GitHub, the suites themselves.
- If the system beats an official record, that sentence, written as a win: "Run before the release, Floodplain finds the three breaks users hit, and Nemotron writes the one-line fix the llm maintainer shipped nine days later."
- RED: no.

## 7. Sponsor surface [check 6, rules 72, 88, 97, 105]
- The sponsor's primitive (models, APIs, tools, SDK features, managed services, data volume): Token Factory Sandboxes (forks of content-addressed images) and Nemotron models.
- Every service and bonus item the brief lists, with my planned use beside each: Token Factory inference: Nemotron 3 Nano (triage), Super and Ultra (fixer agent, Ultra for escalation as the brief recommends); Token Factory Sandboxes: every fork, about 1,000 sandbox runs; Serverless Jobs and Endpoints: encouraged for the Apps track, not required for Coding; not used, and the watcher runs as a GitHub Actions schedule instead; Tavily (bonus): search and extract for migration guidance, guarded and cached.
- Winners' or nearest neighbours' count of that primitive, against my planned count: nearest neighbours use one Nemotron tier and one sandbox per task (Apollo, faultline); mine uses all three Nemotron tiers, three-way forks plus a fork per patch attempt, and Tavily. 0 of 366 public entries run dependents' suites.
- Data size, against what the sponsor's product is for: 146 real third-party packages, each three forks, plus 31 pre-release runs and every fix attempt in its own fork. Sandboxes exist for exactly this fan-out.
- The ablation (same task, sponsor switched off) and what I expect it to show: without Sandboxes there is no result at all; without Nemotron there is no patch. Fix rounds already compare guidance sources (OpenAI's guide against Tavily pages), reported separately.
- RED: no.

## 8. The crowd, measured [check 7, rules 30, 71, 94, 99]
- Gallery search terms, and how many taglines state my thesis (or funded products, if the gallery is dark): gallery dark. GitHub trail: about 15 of 47 "nebius sandboxes" repos are "fork a sandbox, propose a patch, verify it", the track's own question. Searches for dependents, downstream, reverse dependencies: 0 other entries.
- Did that crowd win last time? The biggest neighbour's size number, against mine: no previous edition. Apollo (319 commits) runs one npm package at a time on the consumer side; Floodplain ran 146 dependents of one release.
- devpost.com/stephensookra checked (Devpost events): Stephen Sookra's entry is reproof (memory-safety triage, 131 commits), a different job.
- RED: no. The lane is the track's own framing (terrain, sixth lesson); the sentence nobody else can say is that it runs the dependents' own test suites, before the release.

## 9. Who pays the sponsor [check 8, rules 69, 70, 78]
- Who pays the sponsor, and does this make them buy more: developers and companies buying Token Factory inference and sandboxes. One check is about 450 sandbox runs and a few hundred thousand Nemotron tokens; every release repeats it.
- Would the sponsor's sales team show it on Monday: yes: "fork one checkout three ways" is the Sandboxes pitch, run on 146 real projects. The 500s are in FEEDBACK.md, never the headline.
- RED: no.

## 10. Traps and name [check 2, rules 40, 44, 63, 100]
- User and subject (if different, is the subject a person being measured): user is the upstream maintainer; subject is code (dependents' test suites). No person is measured.
- The genre in three seconds, "it is X but with Y": Rust's crater for Python packages, with an agent that writes the fixes.
- Name checked in the package registry, GitHub, the hackathon gallery and my own projects: renamed from "Downstream" (live on PyPI) on 2026-10-19; "floodplain" checked on PyPI, GitHub and my projects (rule 100).
- RED: no.

## 11. Pitch and tagline [check 4, rules 56, 104]
- "[person] can [want] and [outcome with a price on it]": an open-source maintainer about to publish can see whose test suites the release breaks, and get a patch for each that the project's own tests pass, before their users lose nine days.
- Tagline draft, leading with the best result as a win: Run before openai 3.0.0, it found the three packages the release broke, and Nemotron wrote the fix llm's maintainer shipped nine days later.

## 12. Demo [rules 25, 54, 101]
- The final shot (the thing the verb produces, or a live success landing in field 5's system, never a number being revealed): the verified llm patch beside the line its maintainer shipped, then the agent's own steps fixing agno, then the GitHub issue the watcher opened for openai 3.37.0.
- The first live end-to-end success, on real data, with the sponsor's model in the loop, by (date, day 3 at the latest): 2026-10-20, llm's patch verified on Nebius Sandboxes.

## Verdict

**Verdict:** GO

Fixes made for each RED:
- Field 1: resolved by time; Watermark was submitted on 2026-10-22 and Floodplain is the only build left in the window.
- Field 4: the fixer is now an agent loop (src/floodplain/agent.py) that picks its own tool at every step. Revisions 3 to 8 were each measured on 5 runs per package; revision 8 ships, verifying agno 5 of 5 and vlmrun 5 of 5, and llm 0 of 5, which the README and the page both state.
- Field 5: `floodplain watch` and `floodplain check` write the report into GitHub, and .github/workflows/watch.yml runs the watcher every day. Its first live run checked openai 3.37.0 (30 dependents, none of the 21 working suites broke, one flaky test confirmed and set aside) and opened the issue.
