# Filing change tracker

Compare annual Risk Factors and MD&A, inspect cited changes, and save a research memo locally. Python 3.9+; no API key, paid service, database, or application dependencies.

## Open the review app

Run from this folder:

```sh
python3 -m filing_tracker serve corpus/msft-2023-2024.json \
  --assumptions corpus/example-assumptions.json --out reviews/microsoft --port 8874
```

Open http://127.0.0.1:8874. Select a passage to see highlighted earlier/later text, numeric comparisons, source links, and matching uncertainty. Save priorities, notes, dismissals, or corrected matches. Assumptions are editable and saved with the review. The example assumptions are hypotheses to replace with your own.

Restart with the same output directory to resume. `review-state.json` contains the authoritative revision history; `report/` contains derived memo, CSV, JSON, and cited source snapshots. The server binds only to localhost. A saved review is tied to exact source hashes. Use a different directory for each pair.

## What is included

- Microsoft FY2022, FY2023, and FY2024 original issuer DOCX filings, plus Berkshire FY2023 and FY2024 issuer PDF filings. Originals, converted text, publisher URLs, accession metadata, and hashes are bundled under `corpus/`.
- Subsection and neighboring-text alignment, adjacent paragraph split/merge matching, and explicit uncertain matches.
- Keyword links to editable investment assumptions; the analyst supplies interpretation.
- Conservative annual numeric comparisons, units, percentage-point changes, and date-rollover suppression. Ambiguous cases remain for review.
- Browser review, corrections, persisted history, memo/CSV export, source-only manual view, and review-session timing.
- Fifty source-grounded author labels, a reserved second-issuer sample, original fictional regression fixtures, and blank independent-review packets.

Read [the implementation plan](PLAN.md), [measured results and limitations](docs/v2-results.md), and [source provenance](docs/source-access.md).

## Export without a browser

```sh
python3 -m filing_tracker compare corpus/msft-2023-2024.json \
  --assumptions corpus/example-assumptions.json --out demo/real-microsoft
python3 -m filing_tracker compare corpus/brk-2023-2024.json --out demo/real-berkshire
```

Open [the Microsoft memo](demo/real-microsoft/memo.md). Every source excerpt links to a local snapshot with original-document locators. Source snapshots link to the preserved DOCX/PDF. Full source text stays separate from interpretation.

## Verify

```sh
python3 verify.py
python3 scripts/benchmark.py
python3 scripts/review_packet.py
python3 scripts/session_summary.py reviews/microsoft/review-state.json
```

`verify.py` records commands, statuses, and results in `verification.json`. Tests bind an ephemeral localhost port, so a sandbox may require network permission. The benchmark compares frozen v1 and v2 on the same author sample. `evaluate` remains available for the complete fictional gold fixtures; real sampled labels use `scripts/benchmark.py`.

Optional browser verification uses an existing Playwright installation and a **disposable** review server. It changes decisions and records test sessions; never run it against a human measurement directory:

```sh
python3 -m filing_tracker serve fixtures/development-pair.json --out /tmp/filing-browser-check --port 8873
# In another terminal, with Playwright available:
REVIEW_URL=http://127.0.0.1:8873 node scripts/browser-check.cjs
```

Regenerating the converted corpus uses `python3 scripts/prepare_corpus.py` and requires Poppler's `pdftotext`. Reading the bundled corpus does not require Poppler. The optional SEC fetch command remains available through `python3 -m filing_tracker fetch --help`; issuer-hosted copies are distinctly identified.

## Evidence limits

The September 22 revision recovered 46/46 sampled changed decisions, compared with 42/46 for v1. This uses corrected author labels, including a Berkshire paragraph split previously mislabeled as an addition. These previously inspected samples are development evidence, not a fresh holdout or whole-filing accuracy estimate. Top-ten coverage of important changes remains weak. Independent importance judgments and human time savings are **not yet validated**; the packet and session workflow are ready for that work. See the [current completion audit](docs/completion-audit.md).

PDF columns, tables, and page breaks can create misleading paragraph boundaries. Automatic grouping handles only two adjacent paragraphs. Numeric interpretation is deliberately limited to supported narrative metrics; there is no XBRL reconciliation, semantic model, OCR, 10-Q support, or claim of financial materiality.
