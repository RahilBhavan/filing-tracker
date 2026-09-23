# Current measured results

These numbers come from the latest `python3 scripts/benchmark.py` run, recorded with code hashes, misses, and timings in [real-benchmark.json](real-benchmark.json). The September 21 V2 release results, including the original labels and the reserved-pair freeze, are preserved as a historical record in [v2/results.md](v2/results.md). What V2 delivered is described there and in [the plan](../PLAN.md).

## Author-labelled sample

A correct detection requires the exact old/new block group and change type. These are purposeful author labels, not randomly sampled or independent ground truth. One Berkshire label was corrected from a standalone addition to a paragraph split after inspecting both originals; that correction is not an algorithm improvement. Unlabelled predictions are neither false positives nor irrelevant items. The two Microsoft pairs share FY2023, so they are not independent experiments.

| Pair | Labelled changes | V1 recovered | V2 recovered | V2 important recovered | Important in V2 top 10 | V2 label decisions needing correction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Microsoft FY2022→2023 | 19 | 18 | 19 | 12/12 | 2/12 | 0 |
| Microsoft FY2023→2024 | 19 | 18 | 19 | 10/10 | 0/10 | 0 |
| Berkshire FY2023→2024 | 8 | 6 | 8 | 6/6 | 1/6 | 0 |
| Total | 46 | 42 | 46 | 28/28 | 3/28 | 0 |

Including unchanged controls, V2 matches 50/50 exact decisions and V1 matches 46/50. V1 recovers 25/28 important changes and leaves 4 label decisions needing correction. Label decisions needing correction are a diagnostic count, not measured clicks or analyst effort.

Ranking remains weak: only 3/28 labelled important changes appear across the three V2 top-ten lists. Of 30 top-ten entries, 4 have author labels and 0 of those are known irrelevant; 26 remain unjudged, so no queue-wide noise rate can be inferred.

Machine comparison times for V2 in the recorded run were 1.23s, 1.37s, 3.41s. They vary per run, exclude human reading, and do not imply analyst time savings.

## Development data, not a holdout

Berkshire was reserved until the V2 implementation was frozen; [v2/holdout-freeze.json](v2/holdout-freeze.json) records those code hashes. Comparison, ranking, parsing, and numeric changes **have** followed that first score: the September 22 matching and ranking revision, and the September 23 fixes to running page headers and narrative fact extraction. The current code no longer matches the freeze hashes. All three pairs are now development data, and a fresh holdout claim needs a new, untouched issuer/year pair.

## Known limits

- PDF layout yields many small table/column blocks and page-split paragraphs; Berkshire produces 878 comparison rows and Microsoft 392 in the current [demo reports](../demo/real-berkshire/memo.md). Every source block remains inspectable, but conversion boundaries can create noise.
- Automatic grouping is limited to two adjacent paragraphs. Lexical rules cannot reliably resolve semantic rewrites.
- Numeric coverage is deliberately narrow. Table rows, multiple metrics in one sentence, unsupported currencies, nonannual periods, and duplicate quantities trigger abstention. An inferred document year is marked; arithmetic does not establish constant scope, materiality, or accounting comparability.
- The browser's manual mode hides model results, but the same local application can access them. Independent reviewers must follow the blind-review protocol; this is not a locked experimental environment.

## Verification

- `python3 verify.py`: exit 0, 54 tests passed, followed by four synthetic comparison/evaluation commands. Output is in [verification.json](../verification.json).
- `python3 scripts/benchmark.py`: exit 0; all six engine/pair results saved to [real-benchmark.json](real-benchmark.json).
- Browser checks, publication inspection, and remaining acceptance gates: [completion audit](completion-audit.md).

## Human validation still required

Have another reviewer complete the source-only packet before seeing the author labels, and resolve disagreements with a second person. Counterbalance manual and assisted sessions on different pairs, grade accuracy, then compare time and corrections. See [the protocol](../corpus/blind-review/README.md). No independent reviews or human sessions are complete.
