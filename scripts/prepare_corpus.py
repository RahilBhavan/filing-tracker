"""Convert pinned issuer originals and create reproducible local manifests."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from filing_tracker.core import digest
from filing_tracker.source_formats import convert

SOURCES = [
    ("msft", 2022, "789019", "Microsoft Corporation", "06-30", "2022-07-28", "0001564590-22-026876", "docx", "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/MSFT_FY22Q4_10K"),
    ("msft", 2023, "789019", "Microsoft Corporation", "06-30", "2023-07-27", "0000950170-23-035122", "docx", "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/MSFT_FY23Q4_10K"),
    ("msft", 2024, "789019", "Microsoft Corporation", "06-30", "2024-07-30", "0000950170-24-087843", "docx", "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/MSFT_FY24Q4_10K"),
    ("brk", 2023, "1067983", "Berkshire Hathaway Inc.", "12-31", "2024-02-26", "0000950170-24-019719", "pdf", "https://www.berkshirehathaway.com/2023ar/202310-k.pdf"),
    ("brk", 2024, "1067983", "Berkshire Hathaway Inc.", "12-31", "2025-02-24", "0000950170-25-025210", "pdf", "https://www.berkshirehathaway.com/2024ar/202410-k.pdf"),
]


def main():
    corpus = ROOT / "corpus"
    documents = {}
    for ticker, year, cik, name, end, filed, accession, extension, url in SOURCES:
        identifier = "%s-%s" % (ticker, year)
        raw = corpus / "originals" / (identifier + "." + extension)
        output = corpus / "converted" / (identifier + ".html")
        convert(raw, output)
        documents[identifier] = {"id": identifier, "company": name, "cik": cik, "form": "10-K",
            "fiscal_year": year, "period_end": "%s-%s" % (year, end), "filed": filed, "accession": accession,
            "path": "converted/" + output.name, "sha256": digest(output.read_bytes()),
            "original_path": "originals/" + raw.name, "original_sha256": digest(raw.read_bytes()),
            "source_url": url, "source_format": extension,
            "filing_index_url": "https://www.sec.gov/Archives/edgar/data/%s/%s-index.htm" % (cik, accession),
            "retrieved_on": "2026-09-21", "conversion": "source_formats v2; OOXML paragraphs" if extension == "docx" else "source_formats v2; pdftotext -bbox-layout"}
        print(identifier, raw.stat().st_size, "original bytes")
    for name, ids, role in [
        ("msft-2022-2023", ["msft-2022", "msft-2023"], "development"),
        ("msft-2023-2024", ["msft-2023", "msft-2024"], "development"),
        ("brk-2023-2024", ["brk-2023", "brk-2024"], "holdout"),
    ]:
        manifest = {"schema_version": 1, "provenance": "issuer", "evaluation_role": role,
                    "note": "Issuer-hosted 10-K copies; converted text is not byte-identical to SEC HTML.",
                    "documents": [documents[x] for x in ids]}
        (corpus / (name + ".json")).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
