# Evaluation and verification

Measured locally on September 21, 2026 with Python 3.9.6. All document content and labels in this evaluation are synthetic and authored for this project. These results measure a small deterministic example corpus, not accuracy on SEC filings or investment performance.

## Corpus and protocol

The development pair compares fictional FY 2023 and FY 2024 documents with 16 and 17 extracted blocks. Its 19 gold decisions contain 16 changes and 3 unchanged controls. The challenge pair compares FY 2024 and FY 2025 with 17 and 18 blocks. Its 19 decisions contain 15 changes and 4 unchanged controls. Across the two pairs there are 31 labeled changes.

Labels identify the expected old block, new block, change type, importance, and a short rationale. Gold source identifiers are independent of generated comparison IDs. Evaluation requires every source block to be covered exactly once. The labels were manually specified from the authored passages before running evaluation. The development numeric-rollover failure informed the matching implementation. Both pairs were inspected during development, share FY 2024, and share one author; challenge is not a blind or statistically independent holdout.

A true positive requires an exact old/new block pairing and correct added, removed, or changed type. A missed rewrite predicted as separate removal and addition therefore produces one false negative and two false positives. This strict rule penalizes incorrect pairing even though the user can still see both passages. This is block-level evaluation. There is no independently labeled span-level precision or recall benchmark.

## Measured uncorrected baseline

| Metric | Development | Challenge |
| --- | ---: | ---: |
| Gold changes | 16 | 15 |
| Predicted changes | 16 | 17 |
| True positives | 16 | 13 |
| False positives | 0 | 4 |
| False negatives | 0 | 2 |
| Change precision | 16/16 = 100% | 13/17 = 76.47% |
| Change recall | 16/16 = 100% | 13/15 = 86.67% |
| Gold alignment and type decisions recovered | 19/19 = 100% | 17/19 = 89.47% |
| Review-worthy items in top 5 | 5/5 = 100% | 3/5 = 60% |
| Review-worthy items in top 10 | 9/10 = 90% | 6/10 = 60% |
| High-priority gold changes recovered in top 10 | 6/7 = 85.71% | 4/6 = 66.67% |
| Local citation checks passed | 33/33 | 35/35 |

Precision at k counts correctly paired changes labeled importance 1 or 2. The denominator is the number of returned items up to k; both pairs return at least ten. High-priority recall uses importance 2. Importance labels are author judgments and have not been validated by a finance expert.

The JSON field `alignment_and_type_accuracy` reports gold decision recovery with gold decisions as its denominator. It includes unchanged decisions and is not a true-negative classification accuracy. Pair precision separately penalizes extra predictions.

Citation integrity checks that every non-null source side has an existing HTML anchor and an exact match to its normalized text offsets. This verifies local traceability. It does not establish source authenticity, correct finance interpretation, or successful SEC access.

Raw counts, missed decisions, and unexpected predictions are in [development metrics](../../demo/development/metrics.json) and [challenge metrics](../../demo/challenge/metrics.json). No reviewer overrides are used for these results.

## Failure analysis

The original character matcher split an ordinary revenue update because repeated amounts and years anchored the wrong clause. Token matching alone still failed that case. Candidate scoring now masks digit tokens while keeping all original evidence and edits intact. A regression test checks that the amounts and periods align as a changed block.

The challenge competition rewrite shares too little wording with the prior paragraph. The litigation disclosure also changes too much when discovery becomes settlement. Both fall below the match threshold. Each becomes an addition and removal, accounting for all four false positives and both false negatives. The unmatched risk additions score 90, which wrongly pushes them above some correctly matched items.

Ranking also misses domain context. In development, supplier concentration rises from 40% to 65%, but the generic numeric rule leaves it outside the top ten. A routine fiscal-year rollover occupies a top-ten slot. In challenge, suspended repurchases lack a dedicated ranking rule and remain below the top ten. These are observed limits, not claims that the model can determine materiality.

The example [review file](../../fixtures/challenge-review.json) explicitly joins the competition and litigation pairs and promotes the buyback. Its [reviewed report](../../demo/reviewed/memo.md) contains 12 changed, 2 added, 1 removed, and 4 unchanged decisions. This demonstrates correction, not improved automatic accuracy.

## Verification commands

Run from the project folder. Each command below completed with exit status 0. `python3 verify.py` records commands, stdout, stderr, Python version, and exit statuses in [verification.json](verification.json).

```sh
python3 -m unittest discover -s tests -v
python3 -m filing_tracker compare fixtures/development-pair.json --out demo/quickstart
python3 -m filing_tracker evaluate fixtures/development-pair.json --gold fixtures/development-gold.json --out demo/development
python3 -m filing_tracker evaluate fixtures/challenge-pair.json --gold fixtures/challenge-gold.json --out demo/challenge
python3 -m filing_tracker compare fixtures/challenge-pair.json --review fixtures/challenge-review.json --out demo/reviewed
```

The test suite has 29 tests. It covers section boundaries, table-of-contents selection, hidden HTML, inline XBRL text, table units, exact offsets, reorder and duplicate handling, numeric and negation changes, mismatched manifests and hashes, reviewer corrections, stale and malformed review files, report links, stale evaluation cleanup, CSV formula escaping, CLI exits, and mocked SEC ingestion.

## Deviations and remaining limits

- Real SEC retrieval failed; the demo and measured evaluation use explicitly synthetic fixtures. The optional network loader is verified with mocks only. The attempted download and exit statuses are in [source access](../source-access.md).
- The memo is a source-excerpt draft with visible rule explanations. It does not synthesize an investment recommendation or generate financial claims with a language model.
- Review uses editable JSON rather than a graphical interface. Every changed item begins in a needs-review state. Dismissed items remain in exports as an audit trail.
- The parser is an HTML block baseline. It has no OCR, cross-page reconstruction, colspan or rowspan accounting semantics, or robust support for all issuer layouts. It can miss sections or choose a wrong long candidate; warnings and source inspection remain necessary.
- Alignment is greedy, lexical, and one-to-one within sections. Split paragraphs, merged paragraphs, cross-section moves, paraphrases, and duplicated boilerplate can fail. Scores are not calibrated confidence estimates.
- The loader infers a fiscal-year label from the reporting date's calendar year. Unusual issuer fiscal-year naming, transition years, and amendments need manual treatment. Local manifests assert source metadata; hashes detect byte changes, not provenance fraud.
- Numeric ranking does not normalize units, distinguish year-to-date amounts, calculate comparable growth, or estimate materiality. No valuation, stock-price reaction, real analyst review time, or time savings was measured.
- The two pairs provide 38 author-labeled decisions with no confidence intervals or independent annotator agreement. Larger real-document testing is required before claiming general accuracy.

Original planning notes and first exercise remain unchanged outside this project folder. No deployment, publication, external messaging, or optional paid model integration was performed.
