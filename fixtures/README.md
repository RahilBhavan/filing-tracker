# Fictional corpus and labels

These are author-created synthetic annual disclosures for Alder Components Example Co. They are not real 10-K filings or SEC facts. The year, filing date, accession identifier, and company metadata are invented.

`development-pair.json` compares 2023 with 2024. `challenge-pair.json` compares 2024 with 2025. Each manifest pins the original HTML with SHA-256 hashes. Each gold file contains 19 manually specified alignment and change-type decisions. There are 16 changed decisions in development and 15 in challenge; unchanged controls make up the rest.

Gold `old` and `new` fields refer to source DOM IDs, independently of the parser's generated block IDs. Each non-null source ID must be covered exactly once. Importance is 0 for low review value, 1 for review-worthy, and 2 for high-priority review. Each label has a rationale. The labels do not establish financial materiality.

The two pairs share the 2024 document and the same author. The challenge pair is a second test case, not a statistically independent or blind test set. The numeric-rollover failure on development informed the implementation. Substantial rewrite failures remain in the challenge results.

`challenge-review.json` is a worked example of reviewer overrides based on inspecting the fictional passages. It is excluded from baseline evaluation. SHA-256 changes require deliberate updates to the manifests and pair fingerprints before old labels or reviews can be reused.

`page-headers.html` is a small parser fixture with SEC-style running page headers ("Item 1A" repeated on every page), page numbers, and "PART I" rows. It is not a pair.
