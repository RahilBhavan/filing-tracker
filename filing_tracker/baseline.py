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

    def flush(self):
        text = normalize("".join(self.buffer))
        if text:
            self.rows.append({"text": text, "kind": self.kind, "dom_id": self.anchor})
        self.buffer = []
        self.anchor = None
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
        for i, row in enumerate(chosen, 1):
            start = len(extracted)
            extracted += row["text"] + "\n\n"
            blocks.append(dict(row, id="%s-%04d" % (section, i), section=section,
                               index=i, start=start, end=start + len(row["text"])))
    return blocks, extracted, warnings


def load_pair(manifest_path):
    path = Path(manifest_path).resolve()
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise TrackerError("Unsupported manifest schema_version")
        if manifest.get("provenance") not in {"synthetic", "sec"}:
            raise TrackerError("provenance must be synthetic or sec")
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
                         "warnings": warnings, "raw_path": str(raw_path)})
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


def compare(pair, review=None, threshold=0.62):
    review = review or {}
    if not isinstance(review, dict) or set(review) - {"pair_fingerprint", "alignments", "reviews"}:
        raise TrackerError("Review must be an object with pair_fingerprint, alignments, and reviews")
    if not isinstance(review.get("alignments", []), list) or not isinstance(review.get("reviews", {}), dict):
        raise TrackerError("alignments must be a list and reviews must be an object")
    if review and review.get("pair_fingerprint") != pair["fingerprint"]:
        raise TrackerError("Review file belongs to a different filing pair or source version")
    if not 0 < threshold <= 1:
        raise TrackerError("Alignment threshold must be in (0, 1]")
    old_map = {b["id"]: b for b in pair["old"]["blocks"]}
    new_map = {b["id"]: b for b in pair["new"]["blocks"]}
    used_old, used_new = set(), set()
    changes = []
    for override in review.get("alignments", []):
        if not isinstance(override, dict) or set(override) != {"old", "new"}:
            raise TrackerError("Each alignment must specify old and new block IDs or null")
        a, b = override.get("old"), override.get("new")
        if (not a and not b) or (a and a not in old_map) or (b and b not in new_map):
            raise TrackerError("Invalid block reference in alignment override")
        if a in used_old or b in used_new:
            raise TrackerError("A block cannot be used by two alignment overrides")
        old, new = old_map.get(a), new_map.get(b)
        if old and new and old["section"] != new["section"]:
            raise TrackerError("Cross-section alignment is outside this MVP")
        changes.append(make_change((old or new)["section"], old, new, "reviewer"))
        if a:
            used_old.add(a)
        if b:
            used_new.add(b)
    for section in SECTIONS:
        olds = [b for b in old_map.values() if b["section"] == section and b["id"] not in used_old]
        news = [b for b in new_map.values() if b["section"] == section and b["id"] not in used_new]
        for old in olds:
            matches = [b for b in news if b["id"] not in used_new and b["text"] == old["text"]]
            if matches:
                new = min(matches, key=lambda b: (abs(b["index"] - old["index"]), b["id"]))
                changes.append(make_change(section, old, new, "exact", 1.0))
                used_old.add(old["id"])
                used_new.add(new["id"])
        candidates = []
        for old in olds:
            if old["id"] in used_old:
                continue
            for new in news:
                if new["id"] not in used_new:
                    score = similarity(old["text"], new["text"])
                    if score >= threshold:
                        candidates.append((score, old["id"], new["id"]))
        for score, a, b in sorted(candidates, key=lambda x: (-x[0], x[1], x[2])):
            if a in used_old or b in used_new:
                continue
            alternatives = [s for s, x, y in candidates if (x == a or y == b) and (x, y) != (a, b)]
            ambiguous = score < 0.75 or any(abs(score - s) < 0.04 for s in alternatives)
            changes.append(make_change(section, old_map[a], new_map[b], "lexical", score, ambiguous))
            used_old.add(a)
            used_new.add(b)
        for old in olds:
            if old["id"] not in used_old:
                changes.append(make_change(section, old, None, "unmatched", ambiguous=True))
        for new in news:
            if new["id"] not in used_new:
                changes.append(make_change(section, None, new, "unmatched", ambiguous=True))
    by_id = {c["id"]: c for c in changes}
    for identifier, decision in review.get("reviews", {}).items():
        if not isinstance(decision, dict):
            raise TrackerError("Each review decision must be an object")
        if identifier not in by_id:
            raise TrackerError("Review references a change absent after alignment: " + identifier)
        if set(decision) - {"priority", "status", "note"}:
            raise TrackerError("Unknown reviewer field")
        change = by_id[identifier]
        if "priority" in decision:
            if decision["priority"] not in {"high", "medium", "low"}:
                raise TrackerError("Review priority must be high, medium, or low")
            change["priority"] = decision["priority"]
            change["score"] = {"high": 95, "medium": 55, "low": 10}[decision["priority"]]
            change["reasons"].append("Priority set by reviewer")
        if "status" in decision:
            if decision["status"] not in {"accepted", "dismissed", "needs_review"}:
                raise TrackerError("Invalid review status")
            change["status"] = decision["status"]
            change["needs_review"] = decision["status"] == "needs_review"
        if "note" in decision:
            if not isinstance(decision["note"], str):
                raise TrackerError("Review note must be text")
            change["review_note"] = decision["note"]
    changes.sort(key=lambda c: (-c["score"], c["section"], c["id"]))
    return {"schema_version": 1, "pair_fingerprint": pair["fingerprint"],
            "provenance": pair["manifest"]["provenance"], "threshold": threshold,
            "old": pair["old"]["metadata"], "new": pair["new"]["metadata"],
            "sections": {section: {"label": label,
                "old_blocks": sum(b["section"] == section for b in pair["old"]["blocks"]),
                "new_blocks": sum(b["section"] == section for b in pair["new"]["blocks"])}
                for section, label in SECTIONS.items()},
            "warnings": pair["old"]["warnings"] + pair["new"]["warnings"], "changes": changes}
