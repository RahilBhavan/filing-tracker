# V2 delivery and measured results

Implemented September 21, 2026. All six engineering workstreams in [the plan](../PLAN.md) are delivered. Independent human labels, a fully judged top-ten noise rate, and human time-saving validation remain pending.

## Delivered

1. Five official issuer filings, three successive Microsoft years and two Berkshire years with a different format. Originals and converted views have verified hashes and block-level locators. Fifty author-labelled decisions were created from source text before evaluating those pairs.
2. Contextual lexical matching uses subsection and neighboring exact anchors, preserves reordered exact matches, supports two adjacent split/merged paragraphs, and flags uncertainty. Manual corrections support larger consecutive groups.
3. Editable memo assumptions have explicit terms and priorities. Matching disclosures receive transparent relevance links and a bounded priority boost. The app makes no automatic support/contradiction claim.
4. Narrative quantities carry metric, unit, role, period, and period-evidence fields. Comparable annual quantities produce absolute or percentage-point changes; unsupported tables, currencies, periods, and duplicate quantities trigger abstention. Date-only rollover is low priority.
5. A localhost browser app provides highlighted side-by-side excerpts, source snapshots, editable matching, priority, status, notes, assumptions, revision checks, and persisted history. Reports include every member's citation in grouped matches.
6. A repeatable v1/v2 benchmark reports important-change recall, strict alignment corrections, top-ten judgement coverage, and machine comparison time. Source-only independent-review packets and timed manual/assisted sessions are available. Human timing remains unmeasured.

## Real source sample

A correct detection requires the exact old/new block group and change type. These are purposeful author labels, not randomly sampled or independent ground truth. Unlabelled predictions are neither false positives nor irrelevant items. The two Microsoft pairs share FY2023 and therefore are not independent experiments.

| Pair | Labelled changes | V1 recovered | V2 recovered | V2 important recovered | Important in V2 top 10 | Label decisions needing correction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Microsoft FY2022→2023 | 19 | 18 | 18 | 11/12 | 2/12 | 1 |
| Microsoft FY2023→2024 | 19 | 18 | 18 | 9/10 | 0/10 | 1 |
| Berkshire FY2023→2024 | 8 | 6 | 6 | 5/6 | 1/6 | 2 |
| Total | 46 | 42 | 42 | 25/28 | 3/28 | 4 |

Four unchanged controls bring the label total to 50. V2 recovers 46/50 exact decisions. The features improve the review workflow, but this sample demonstrates **no aggregate detection gain**. Important-change ranking is weak: the queue should not be treated as an exhaustive short list.

Only 3, 0, and 1 items in the respective global top tens have exact author labels. Their known irrelevant counts are zero, but 26/30 top-ten entries remain unjudged. A whole-queue noise rate cannot be inferred. Label decisions needing correction are a diagnostic count, not measured clicks or analyst effort.

Full counts, misses, timings, and code hashes: [real-benchmark.json](real-benchmark.json). Machine comparison times in the recorded run were approximately 0.91s, 1.10s, and 3.26s for V2; these exclude human reading and do not imply analyst time savings.

## Reserved pair protocol

Berkshire was excluded from scoring/tuning until the comparison implementation was frozen. Its layout and source passages were inspected for conversion and author labels before the freeze; it was not completely unseen data. [holdout-freeze.json](holdout-freeze.json) records the code hashes and protocol before the first Berkshire comparison. No comparison/ranking changes followed that score. UI, documentation, and tests were finalized afterward.

## Known failures and limits

- Microsoft effective-tax passages are classified as a removal plus addition instead of one changed match in both pairs.
- Berkshire's expanded cybersecurity heading is also split into a removal/addition. Its new insurance-liability paragraph is grouped into neighboring disclosure instead of the labelled standalone addition.
- PDF layout yields many small table/column blocks and page-split paragraphs; Berkshire produced 881 comparison rows from 678 blocks per year. Every source block remains inspectable, but conversion boundaries can create noise.
- Automatic grouping is limited to two adjacent paragraphs. Lexical rules cannot reliably resolve semantic rewrites. Generic liquidity/modal rules can outrank useful annual operating metrics.
- Numeric coverage is deliberately narrow. An inferred document year is explicitly marked; arithmetic does not establish constant scope, materiality, or accounting comparability. Bare four-digit year normalization and unsupported narrative metrics still require judgment.
- The browser's manual mode hides model results, but the same local application can access them. Independent reviewers must follow the blind-review protocol; this is not a locked experimental environment.

## Verification evidence

- `python3 verify.py`: exit 0. **41 tests passed**, followed by four successful synthetic comparison/evaluation commands. Exact command output is in [verification.json](../verification.json).
- Real corpus loading checks original/converted SHA-256 and every extracted block's normalized source span. Group-correction tests verify all member citations.
- Browser verification: exit 0, no page errors. Checked highlighted edits, decision persistence, assumption save, session start/finish, matching save, citation HTTP access, 390px layout without horizontal overflow, and manual reading. The browser test used disposable synthetic state; its timings are not human measurements.
- `python3 scripts/benchmark.py` equivalent `benchmark.run('.')`: exit 0; all six engine/pair results saved. Both real report-export commands exited 0.
- `python3 scripts/review_packet.py`: exit 0. Blank decisions and complete source passages are in [blind-review](../corpus/blind-review/README.md).
- Berkshire 2024 page 27 was rendered and visually inspected for source order. No full visual audit of all PDF pages was performed.

Earlier checks caught and resolved a mismatched test search term, missing accessible control labels, and browser-test URL/revision assumptions. Loopback tests needed sandbox permission; the final permitted run passed. Port 8765 was occupied, so browser verification used 8873.

Additional check records: [v2-verification.json](v2-verification.json). Screenshot: [real Microsoft review](review-preview.png).

## Human validation still required

Have another reviewer complete the source-only packet before seeing the author labels. Resolve disagreements with a second person. Counterbalance manual and assisted sessions on different pairs, grade accuracy, then compare time and corrections. See [the protocol](../corpus/blind-review/README.md). No independent reviews or human sessions are claimed complete.
