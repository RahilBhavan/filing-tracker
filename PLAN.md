# Version 2 implementation plan

Requested scope: execute all six improvements from the discussion. Keep the app local, deterministic, and free of paid API requirements. Preserve the original planning notes and fictional regression corpus.

1. Obtain three successive official annual filings for one company and an annual pair from a second company with a different layout. Store originals, source URLs, hashes, and exact reporting periods. Reserve one real pair for a final evaluation after the implementation is frozen. Prepare 30–50 source-grounded labels before evaluating predictions.
2. Add subsection and neighboring-block context to alignment. Support adjacent split and merged paragraphs without losing original source references. Retain explicit uncertainty and unchanged reorder handling.
3. Add editable investment assumptions and transparent links from each relevant change to the assumption it might affect. Preserve evidence separately from the analyst's thesis.
4. Add conservative numeric extraction with units, annual periods, changes in comparable amounts, and percentage-point changes. Suppress routine date-only changes. Abstain when metric, unit, or period comparability is ambiguous.
5. Add an accessible local browser interface for side-by-side excerpts, highlighted edits, source links, matching corrections, priority changes, dismissal, persisted review history, and memo assumptions.
6. Evaluate detection, important-change recall, top-ten noise, and correction counts. Provide a blind annotation packet and timed manual/assisted review sessions. Report machine measurements separately from human judgments and timing.

Verification will cover existing regressions, real document extraction and source traceability, grouping and numeric edge cases, review persistence, local HTTP boundaries, and browser interactions. Save exact commands, exit statuses, raw evaluation counts, and known failures.

Independent human labels and analyst time-savings claims require another person's completed review. Build the packet and measurement workflow now; never substitute author labels or automated timing for that evidence.

Status at start: planned. Completion evidence and any remaining human validation will be recorded in docs/v2-results.md.

## Final status

- [x] Official real sources, conversions, hashes, 50 author labels, and reserved-pair protocol.
- [x] Contextual and adjacent split/merge matching with uncertainty and original member citations.
- [x] Editable assumptions and transparent relevance links.
- [x] Conservative unit/period-aware numeric comparisons and abstentions.
- [x] Local browser review, corrections, exports, saved history, and sessions.
- [x] Reproducible engine comparison, source-only packets, and human measurement workflow.
- [ ] Independent human labeling, complete top-ten relevance judgments, and accuracy-controlled human timing study. Requires actual reviewers; no substituted measurements.

Engineering verification at the September 21 release: 41 Python tests and browser interactions passed, and both engines recovered 42/46 author-sample changes ([historical results](docs/v2/results.md)). Current status: 54 Python tests pass, V2 recovers 46/46 changed decisions and V1 42/46 on the corrected labels; see [current results](docs/v2-results.md) for limitations. These pairs are now development data, not a holdout.

## Completion follow-up — September 22

1. Correct numeric direction, mixed-metric attribution, and monetary/date handling; add regression tests.
2. Preserve review drafts across saves, navigation, and reloads; verify in the browser.
3. Improve evidence-based ranking and matching, rerun the author benchmark, and preserve historical scores. Previously viewed pairs are development data for this revision.
4. Make independent labels and top-ten judgments importable and validate real session evidence without substituting automated measurements.
5. Run Python and browser verification, inspect publishable files, and push to the user's GitHub destination. Keep personal review state out of Git.

Human review and accuracy-controlled timing require completed reviewer submissions. These remain explicit release gates.
