# Walk through one filing comparison

Start from the project folder with Python 3.9 or later. You will inspect a numeric change, a negation, a reordered passage, and a missed match, then correct the result using JSON.

## Run the annual pair

Run `python3 -m filing_tracker compare fixtures/development-pair.json --out demo/quickstart`. Open `demo/quickstart/memo.md`.

The selected documents represent fictional FY 2023 and FY 2024 filings for Alder Components Example Co. The manifest labels the entire pair `synthetic`. Its CIK and accession identifiers also say SYNTHETIC. This keeps the evidence category visible in the source, metadata, memo, and CSV.

Each filing has an Item 1A Risk Factors section and an Item 7 MD&A section. The parser excludes later items. In the section table, expect 8 old risk blocks and 9 new ones, plus 8 MD&A blocks on each side.

## Follow the evidence

Find the credit facility passage. The newer text adds "not" before "in compliance." Open both source links and check the excerpts. This one-word edit changes the meaning, so the rule assigns high review priority.

Find the revenue passage. The old source says $120 million for 2023; the new source says $135 million for 2024. Both quoted passages retain their comparison years and units. A generic numeric-change rule flags the edit. You must still decide which figures are comparable.

Open `demo/quickstart/comparison.json` and inspect the `edits` array for one change. Each edit has half-open character offsets and exact text for both sides. Those offsets are relative to that block. Source blocks also have document-level offsets into the neighboring normalized `.txt` file. Neither offset is a location in raw HTML.

The HTML snapshot links to the original local HTML and records its SHA-256. A hash detects changed source bytes; it does not prove who authored the document. A real SEC pair also includes the SEC document URL.

## Check reordered text

Find the competition passage in `demo/quickstart/changes.csv`. It is unchanged, despite appearing earlier in the second filing. Exact matching runs across the section before approximate matching, so paragraph order does not turn the passage into an addition.

The `moved` field means its ordinal block position changed. Insertions can shift positions too; the field does not prove a deliberate editorial move.

## Correct the challenge pair

Run `python3 -m filing_tracker compare fixtures/challenge-pair.json --out demo/challenge` and open its memo. The baseline misses the connection between the broad competition statement and a new description of rivals bundling maintenance. It also fails to join discovery-stage litigation with a settlement description.

Copy `demo/challenge/review.json` to a new JSON file. Preserve its `pair_fingerprint`. Add these alignment entries:

```json
"alignments": [
  {"old": "risk-0001", "new": "risk-0005"},
  {"old": "risk-0006", "new": "risk-0006"}
]
```

These IDs come from the two source snapshots. They are unique within each document; "old" and "new" distinguish the sides. To split an incorrect match, force one old block to `null` and one new block from `null`. The validator rejects reuse of a block and cross-section matches.

Run the comparison with `--review` pointing to your file and `--out demo/my-review`. Inspect the new `comparison.json` for the resulting change IDs. Add a `reviews` entry to accept, dismiss, or reprioritize a specific change:

```json
"reviews": {
  "7b768b133e92": {
    "priority": "high",
    "status": "accepted",
    "note": "Example on fictional data: suspension of repurchases warrants review of the capital return assumption."
  }
}
```

That ID is the buyback change for this exact challenge pair. Copy actual IDs for other pairs. Every supplied ID must still exist after alignment overrides; stale decisions produce an error.

Run again. The note appears as reviewer-supplied interpretation. The exact source excerpts remain in the report. To see a complete example, use `fixtures/challenge-review.json` and compare with `demo/reviewed/memo.md`.

## Understand the code through one passage

Read `core.py` in the `filing_tracker` directory, starting with `parse_html`, then `compare`. The parser turns HTML into section blocks. Exact matches consume blocks first. Remaining candidates receive 70% ordered token similarity and 30% token-set overlap, with a default threshold of 0.62. Digits become placeholders only during candidate scoring to avoid matching the wrong repeated year; evidence and edit spans keep the original digits.

Candidates are selected greedily with a deterministic tie-break. A score below 0.75 or a competing match within 0.04 marks uncertainty. Unmatched blocks also need review. These scores are heuristics, not calibrated probabilities.

Then read `rank_change`. Rules select the highest applicable score: base edit 30, numeric edit 60, removed risk 70, outlook 75, financing 80, modal or negation edit 85, added risk 90. High starts at 75 and medium at 50. A reviewer can override priority. The rule explanation remains visible.

Finally read `report.py` and `evaluation.py`. Reports keep source references. Evaluation compares the predicted old/new block pair and change type with separately authored labels. Run `python3 verify.py` after an implementation change.

Your next exercise: choose one missed match, write a test describing the desired behavior, and propose a change that also leaves an unrelated pair unmatched. Evaluate both fixture pairs. Do not claim better real-world accuracy until you have tested real filings and labels from another reviewer.
