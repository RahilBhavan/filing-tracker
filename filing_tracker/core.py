"""Parse annual-filing sections, align blocks, and rank observed edits."""

import hashlib
import json
import re
from collections import Counter
from datetime import date
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path


SECTIONS = {"risk": "Item 1A — Risk Factors", "mda": "Item 7 — MD&A"}
TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
NUMBER = re.compile(r"(?<!\w)[+-]?\d[\d,]*(?:\.\d+)?%?")
MODALS = {"not", "no", "never", "may", "might", "will", "cannot", "could"}


class TrackerError(ValueError):
    pass


def digest(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def normalize(text):
    # Keep all punctuation, numbers, units, case, and negation.
    return " ".join(text.split())


class FilingHTML(HTMLParser):
    """A conservative block reader; unsupported layouts remain an explicit limit."""

    BOUNDARIES = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "section", "article", "br"}
    SKIP = {"script", "style", "head", "ix:hidden", "ix:header", "nav", "header", "footer"}
    VOID = {"br", "hr", "img", "meta", "link", "input", "wbr", "source", "area", "base", "col", "embed", "param"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.buffer = []
        self.rows = []
        self.kind = "paragraph"
        self.anchor = None
        self.locator = None
        self.page = None

    def flush(self):
        text = normalize("".join(self.buffer))
        if text:
            self.rows.append({"text": text, "kind": self.kind, "dom_id": self.anchor,
                              "source_locator": self.locator, "page": self.page})
        self.buffer = []
        self.anchor = None
        self.locator = None
        self.page = None
        self.kind = "paragraph"

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        style = re.sub(r"\s", "", attrs.get("style", "").lower())
        hidden = (any(x[1] for x in self.stack) or tag in self.SKIP
                  or "hidden" in attrs or attrs.get("aria-hidden") == "true"
                  or "display:none" in style or "visibility:hidden" in style)
        if not hidden:
            in_row = any(x[0] == "tr" for x in self.stack)
            if tag in self.BOUNDARIES and not in_row:
                self.flush()
                self.kind = "table_row" if tag == "tr" else "heading" if re.fullmatch(r"h[1-6]", tag) else "paragraph"
            if tag in {"td", "th"} and self.buffer:
                self.buffer.append(" | ")
            if tag == "br" and in_row:
                self.buffer.append(" ")
            if attrs.get("id") and self.anchor is None:
                self.anchor = attrs["id"]
            if attrs.get("data-source-locator"):
                self.locator = attrs["data-source-locator"]
            if attrs.get("data-page"):
                self.page = int(attrs["data-page"])
        if tag not in self.VOID:
            self.stack.append((tag, hidden))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        hidden = any(x[1] for x in self.stack)
        if not hidden and tag in self.BOUNDARIES:
            in_row = any(x[0] == "tr" for x in self.stack)
            if not in_row or tag == "tr":
                self.flush()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not any(x[1] for x in self.stack):
            self.buffer.append(data)


def item_heading(text):
    # Requiring a short row avoids treating prose references as boundaries.
    if len(text) > 180:
        return None
    match = re.match(r"^Item\s+(\d+[A-C]?)\s*[.:|—–-]?\s*(.*)$", text, re.I)
    if not match:
        return None
    item, title = match.group(1).upper(), match.group(2).strip()
    if item == "1A" and (not title or "risk factors" in title.lower()):
        return "risk"
    if item == "7" and (not title or "management" in title.lower()):
        return "mda"
    if item in {"1B", "1C", "2", "3", "4", "5", "6", "7A", "8", "9", "9A", "9B", "9C", "10", "11", "12", "13", "14", "15", "16"}:
        return "stop"
    return None


def parse_html(html):
    parser = FilingHTML()
    parser.feed(html)
    parser.close()
    parser.flush()
    candidates = {key: [] for key in SECTIONS}
    active = None
    current = []

    def save():
        if active and current:
            candidates[active].append(list(current))

    for row in parser.rows:
        boundary = item_heading(row["text"])
        if boundary:
            save()
            active = boundary if boundary in SECTIONS else None
            current = []
        elif active:
            current.append(row)
    save()
    blocks = []
    extracted = ""
    warnings = []
    for section in SECTIONS:
        choices = candidates[section]
        if not choices:
            raise TrackerError("Missing or empty section: " + SECTIONS[section])
        chosen = max(choices, key=lambda rows: sum(len(row["text"]) for row in rows))
        if len(choices) > 1:
            warnings.append("Multiple %s candidates; used the longest nonempty span. Check boundaries." % section)
        subsection = ""
        for i, row in enumerate(chosen, 1):
            if row["kind"] == "heading":
                subsection = row["text"]
            start = len(extracted)
            extracted += row["text"] + "\n\n"
            blocks.append(dict(row, id="%s-%04d" % (section, i), section=section, subsection=subsection,
                               index=i, start=start, end=start + len(row["text"])))
    return blocks, extracted, warnings


def load_pair(manifest_path):
    path = Path(manifest_path).resolve()
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise TrackerError("Unsupported manifest schema_version")
        if manifest.get("provenance") not in {"synthetic", "sec", "issuer"}:
            raise TrackerError("provenance must be synthetic, sec, or issuer")
        if len(manifest["documents"]) != 2:
            raise TrackerError("Select exactly two annual documents")
        docs = []
        for metadata in manifest["documents"]:
            for key in ("id", "company", "cik", "form", "fiscal_year", "period_end", "filed", "accession", "path", "sha256"):
                if key not in metadata:
                    raise TrackerError("Missing document metadata: " + key)
            if not re.fullmatch(r"[A-Za-z0-9_-]+", metadata["id"]):
                raise TrackerError("Document id must be a safe filename")
            if metadata["form"] != "10-K":
                raise TrackerError("MVP requires original 10-K forms, not amendments or quarterly forms")
            if date.fromisoformat(metadata["filed"]) < date.fromisoformat(metadata["period_end"]):
                raise TrackerError("Filing date precedes fiscal period end")
            raw_path = (path.parent / metadata["path"]).resolve()
            raw = raw_path.read_bytes()
            if digest(raw) != metadata["sha256"]:
                raise TrackerError("Source SHA-256 mismatch: " + metadata["id"])
            if manifest["provenance"] == "issuer":
                if not metadata.get("source_url", "").startswith("https://") or not metadata.get("original_path"):
                    raise TrackerError("Issuer copies require an HTTPS source URL and a pinned original")
                original = (path.parent / metadata["original_path"]).resolve()
                if digest(original.read_bytes()) != metadata.get("original_sha256"):
                    raise TrackerError("Original issuer document SHA-256 mismatch")
            if manifest["provenance"] == "sec":
                cik = str(metadata["cik"])
                accession = metadata["accession"]
                if not cik.isdigit() or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
                    raise TrackerError("Invalid SEC identity")
                prefix = "https://www.sec.gov/Archives/edgar/data/%s/%s/" % (int(cik), accession.replace("-", ""))
                if not metadata.get("source_url", "").startswith(prefix):
                    raise TrackerError("SEC source URL does not match CIK and accession")
            blocks, extracted, warnings = parse_html(raw.decode("utf-8"))
            docs.append({"metadata": metadata, "blocks": blocks, "text": extracted,
                         "warnings": warnings, "raw_path": str(raw_path),
                         "original_path": str((path.parent / metadata["original_path"]).resolve()) if metadata.get("original_path") else None})
        old, new = docs
        a, b = old["metadata"], new["metadata"]
        if a["id"] == b["id"] or a["accession"] == b["accession"]:
            raise TrackerError("Choose distinct annual filings")
        if a["cik"] != b["cik"] or a["company"] != b["company"]:
            raise TrackerError("Both documents must belong to the same company and CIK")
        if not (int(b["fiscal_year"]) == int(a["fiscal_year"]) + 1
                and a["period_end"] < b["period_end"] and a["filed"] < b["filed"]):
            raise TrackerError("Select chronological, successive fiscal years")
        fingerprint = digest(json.dumps({"provenance": manifest["provenance"],
            "documents": [{k: v for k, v in d["metadata"].items() if k != "path"} for d in docs]}, sort_keys=True))
        return {"manifest": manifest, "old": old, "new": new, "fingerprint": fingerprint}
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrackerError("Cannot load pair: %s" % exc) from exc


def similarity(a, b):
    a_tokens, b_tokens = TOKEN.findall(a.lower()), TOKEN.findall(b.lower())
    # Only candidate scoring masks digits. Evidence and edit spans retain them.
    # This prevents repeated old/new years from anchoring the wrong clause.
    mask = lambda tokens: ["<number>" if t.isdigit() else t for t in tokens]
    token_ratio = SequenceMatcher(None, mask(a_tokens), mask(b_tokens), autojunk=False).ratio()
    x, y = set(a_tokens), set(b_tokens)
    jaccard = len(x & y) / len(x | y) if x or y else 1.0
    return 0.7 * token_ratio + 0.3 * jaccard


def edit_spans(old, new):
    a, b = list(TOKEN.finditer(old)), list(TOKEN.finditer(new))
    matcher = SequenceMatcher(None, [x.group() for x in a], [x.group() for x in b], autojunk=False)

    def span(tokens, start, end, text):
        if start == end:
            offset = tokens[start].start() if start < len(tokens) else len(text)
            return {"start": offset, "end": offset, "text": ""}
        left, right = tokens[start].start(), tokens[end - 1].end()
        return {"start": left, "end": right, "text": text[left:right]}

    return [{"operation": tag, "old": span(a, i, j, old), "new": span(b, k, l, new)}
            for tag, i, j, k, l in matcher.get_opcodes() if tag != "equal"]


def rank_change(kind, section, old, new):
    if kind == "unchanged":
        return 0, ["Exact text match after whitespace normalization"]
    score, reasons = 30, ["Disclosure text %s" % kind]
    if section == "risk" and kind == "added":
        score = max(score, 90)
        reasons.append("New unmatched risk passage; analyst must confirm novelty")
    if section == "risk" and kind == "removed":
        score = max(score, 70)
        reasons.append("Risk passage no longer matched in this section")
    if kind == "changed":
        if NUMBER.findall(old) != NUMBER.findall(new):
            score = max(score, 60)
            reasons.append("Number tokens changed; period, unit, and significance need review")
        a, b = Counter(TOKEN.findall(old.lower())), Counter(TOKEN.findall(new.lower()))
        if any(a[word] != b[word] for word in MODALS):
            score = max(score, 85)
            reasons.append("Negation or modal wording changed")
    text = (old + " " + new).lower()
    if re.search(r"\b(liquidity|covenant|debt|cash flow|cash flows|credit facility)\b", text):
        score = max(score, 80)
        reasons.append("Liquidity or financing language")
    if re.search(r"\b(outlook|guidance|forecast)\b", text):
        score = max(score, 75)
        reasons.append("Outlook or guidance language")
    return score, reasons


def make_change(section, old, new, method, score=None, ambiguous=False):
    before, after = (old["text"] if old else ""), (new["text"] if new else "")
    kind = "added" if old is None else "removed" if new is None else "unchanged" if before == after else "changed"
    rank, reasons = rank_change(kind, section, before, after)
    identifier = digest("%s:%s:%s" % (section, old["id"] if old else "-", new["id"] if new else "-"))[:12]
    return {"id": identifier, "section": section, "kind": kind, "old": old, "new": new,
            "method": method, "similarity": round(score, 6) if score is not None else None,
            "moved": bool(old and new and old["index"] != new["index"]),
            "needs_review": kind != "unchanged", "ambiguous_alignment": ambiguous,
            "score": rank, "priority": "high" if rank >= 75 else "medium" if rank >= 50 else "low",
            "reasons": reasons, "status": "needs_review" if kind != "unchanged" else "unchanged",
            "review_note": "", "edits": edit_spans(before, after)}



def compare(pair, review=None, threshold=0.62, assumptions=None, engine="v2"):
    if engine == "v1":
        from .baseline import compare as baseline_compare
        result = baseline_compare(pair, review, threshold)
        result["engine"] = "v1"
        return result
    if engine != "v2":
        raise TrackerError("Unknown engine")
    from .alignment import compare_v2
    return compare_v2(pair, review, threshold, assumptions)
