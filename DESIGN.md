# Design

The page is drawn as a hydrogeological dye trace. In a real trace, a hydrologist pours
fluorescein powder into a stream, hangs charcoal packets at every spring and well downstream,
takes a background sample first to rule out natural fluorescence, and later reads which packets
came back green. Floodplain does the same to a package release: the release is poured in
upstream, every dependent is a receptor, the control fork is the background sample, and a
dependent whose own tests broke is a positive.

The look it replaces is the CI dashboard: dark slate, a table of package names with red and
green status dots, a sidebar, KPI columns.

## Laws

Every surface follows these.

1. **Green belongs to a positive and nothing else.** It appears only on a dependent whose suite
   broke against a working baseline, and on that dependent's patch. Not on links, buttons,
   focus rings, passing tests or decoration. In photographs of a dye trace, the dye is the only
   saturated thing in the frame.
2. **Green is poured.** A flat fill with a hard edge: no glow, shadow or gradient, and never a
   text colour on paper. Fluorescein fills the channel bank to bank and stops at the bank.
3. **Text on green is ink**, for contrast, and so the dye reads as a material under the words.
4. **Rust appears once per view, small, at the injection point.** Uranine powder is rust-red
   only before it dissolves.
5. **No status pills and no coloured dots.** A verdict is a receptor state (hung, read, lost,
   never hung), drawn rather than badged.
6. **Every number comes from the data.** Nothing on the page is typed by hand; counts are read
   from the committed results by `scripts/build_site.py`, so a judge can check every one.
7. **Counts use tabular lining numerals** so columns of figures align.
8. **Titles carry no terminal punctuation.**
9. **Logs are shown verbatim, in mono.** An evidence quote is highlighted where it occurs in the
   real log, never paraphrased. A quote Nemotron invented is counted and shown struck out, not
   hidden.
10. **Every non-positive says why, in one line.** No tests shipped, no working baseline, the
    fork returned nothing: each is a sentence, not a grey dash.
11. **One visual language, top to bottom.** The receptor glyph on the river is the glyph in the
    method diagram and in the accounting strip.
12. **The dye shows in the river.** A positive turns its own stretch of the ribbon green, longer
    when more broke. Labels carry a paper halo, as on a survey map, and are placed by measuring
    their width rather than by fixed offsets.
13. **The patch is the climax.** On a dependent's page the diff is the largest object after the
    three sample columns, with the maintainer's own fix beside it when one exists.
14. **No water-height imagery.** No gauges, staffs or flood levels. This page traces where
    something went, not how high it rose.

## Type and colour

Headlines in Source Serif 4, body and map labels in Geologica, logs in Red Hat Mono. Paper
`#ECEDE8`, ink `#1E1F1C`, dye `#94D44A` (`#A6E35A` on the dark theme), rust `#8A2A12`.
