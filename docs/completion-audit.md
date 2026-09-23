# Completion audit — September 22, 2026

The project is a verified local research prototype. It is ready to share as a prototype; research-quality ranking and human validation remain unfinished.

## Verified on the committed implementation

- `python3 -m unittest discover -s tests -q`: exit 0, 47 tests passed in 29.189 seconds. Includes original-file hashes, numeric regressions, grouping, persisted reviews, and localhost boundaries.
- `python3 scripts/benchmark.py`: exit 0; completed all six engine/pair runs. Current raw results are in `real-benchmark.json`.
- `PLAYWRIGHT_MODULE=<installed Playwright> REVIEW_URL=http://127.0.0.1:8893 node scripts/browser-check.cjs`: exit 0; nine checks passed, no page errors. This includes draft preservation across saving assumptions and reloading, persisted decisions, source citations, matching correction, sessions, manual reading, and mobile layout. Used disposable synthetic state, not human study data.
- Publication inspection found no tracked personal review state, environment files, private-key files, or common token patterns. Personal reviews remain ignored.

## Current results and what remains

The current engine recovers 46/46 changed decisions and all 50 exact decisions in the corrected author sample. V1 recovers 42/46 changes. One Berkshire label was corrected from a standalone addition to a paragraph split after inspecting both original passages. That label correction must not be counted as an algorithm improvement. Original labels and scores remain under `v2/`.

Only 3/28 labelled important changes appear across the three global top-ten lists, and 26/30 returned entries remain unjudged. Ranking improvement and complete top-ten relevance judgments remain open. No overall noise rate can be inferred from the current sample.

Independent human labels and accuracy-controlled manual/assisted review timing remain open. There are no completed human sessions. The existing blank packets and timing workflow enable those studies but do not substitute for reviewers. Previously inspected pairs are now development data; a new untouched pair is required for a fresh holdout claim.

PDF table/column boundaries and semantic rewrites remain limitations. Numeric extraction deliberately abstains on mixed-metric sentences. Existing demo reports and earlier verification documents are historical snapshots; regenerate reports with the current CLI when reviewing current behavior.

## Next acceptance gates

1. Judge every returned top-ten entry on each evaluation pair, then improve ranking against predeclared targets.
2. Obtain independent source annotations and reconcile disagreements, preserving original submissions.
3. Evaluate on a new issuer/year pair untouched during development.
4. Complete counterbalanced human sessions and grade answer accuracy before claiming time savings.

No independent validation, human time savings, or production-readiness claim is made.
