"""Optional SEC ingestion. The offline demo never calls the network."""

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .core import TrackerError, digest, load_pair


class SECClient:
    def __init__(self, user_agent):
        if not user_agent or "@" not in user_agent:
            raise TrackerError("Provide an identifying SEC User-Agent containing your contact email")
        self.user_agent = user_agent
        self.last_request = 0.0

    def get(self, url):
        delay = 0.6 - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)
        self.last_request = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read(25_000_001)
            if len(content) > 25_000_000:
                raise TrackerError("SEC response exceeded the 25 MB local limit")
            return content
        except (urllib.error.URLError, TimeoutError) as exc:
            raise TrackerError("SEC access failed; no synthetic substitute was downloaded: %s" % exc) from exc


def rows(column_data):
    keys = ("accessionNumber", "form", "filingDate", "reportDate", "primaryDocument")
    count = len(column_data["accessionNumber"])
    return [{key: column_data[key][i] for key in keys} for i in range(count)]


def fetch_pair(cik, accessions, dest, user_agent, client=None):
    if not re.fullmatch(r"\d{1,10}", str(cik)):
        raise TrackerError("CIK must contain 1 to 10 digits")
    if len(accessions) != 2 or len(set(accessions)) != 2 or any(not re.fullmatch(r"\d{10}-\d{2}-\d{6}", a) for a in accessions):
        raise TrackerError("Supply two distinct, hyphenated accession numbers")
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise TrackerError("Fetch destination must be new or empty; reuse an existing manifest offline")
    client = client or SECClient(user_agent)
    info = json.loads(client.get("https://data.sec.gov/submissions/CIK%010d.json" % int(cik)))
    records = rows(info["filings"]["recent"])
    # Load listed older submission shards so historical pair selection is explicit.
    for shard in info["filings"].get("files", []):
        if not re.fullmatch(r"CIK\d+-submissions-\d+\.json", shard["name"]):
            raise TrackerError("Unexpected historical submission filename")
        records.extend(rows(json.loads(client.get("https://data.sec.gov/submissions/" + shard["name"]))))
    annuals = sorted({r["accessionNumber"]: r for r in records if r["form"] == "10-K"}.values(), key=lambda r: (r["reportDate"], r["filingDate"]))
    selected = [r for r in annuals if r["accessionNumber"] in accessions]
    if len(selected) != 2:
        raise TrackerError("Both accessions must be original 10-Ks in this company's SEC submission history")
    if annuals.index(selected[1]) != annuals.index(selected[0]) + 1:
        raise TrackerError("Selected filings are not successive annual filings in SEC history")
    documents, payloads = [], []
    for r in selected:
        name = r["primaryDocument"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.html?", name):
            raise TrackerError("MVP requires a primary HTML document with a safe filename")
        accession = r["accessionNumber"]
        url = "https://www.sec.gov/Archives/edgar/data/%d/%s/%s" % (int(cik), accession.replace("-", ""), name)
        raw = client.get(url)
        document_id = "sec-" + accession
        documents.append({"id": document_id, "company": info["name"], "cik": str(int(cik)), "form": "10-K",
                          "fiscal_year": int(r["reportDate"][:4]), "period_end": r["reportDate"], "filed": r["filingDate"],
                          "accession": accession, "path": document_id + ".html", "sha256": digest(raw), "source_url": url})
        payloads.append(raw)
    dest.mkdir(parents=True, exist_ok=True)
    for meta, raw in zip(documents, payloads):
        (dest / meta["path"]).write_bytes(raw)
    manifest = dest / "pair.json"
    manifest.write_text(json.dumps({"schema_version": 1, "provenance": "sec", "documents": documents,
                                    "note": "Fiscal year label inferred from report-date year; verify issuer convention."}, indent=2) + "\n", encoding="utf-8")
    # Preserve downloaded originals even if the parser cannot handle their layout.
    load_pair(manifest)
    return manifest
