"""Transparent keyword links to analyst-authored assumptions; no entailment claim."""

import re

from .core import TrackerError


def validate_assumptions(data):
    if data is None:
        return []
    items = data.get("assumptions") if isinstance(data, dict) else data
    if not isinstance(items, list) or len(items) > 30:
        raise TrackerError("Provide at most 30 investment assumptions")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) - {"id", "statement", "terms", "priority"}:
            raise TrackerError("Invalid investment assumption fields")
        if not isinstance(item.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", item["id"]) or item["id"] in seen:
            raise TrackerError("Assumption IDs must be unique and use letters, digits, underscores, or hyphens")
        seen.add(item["id"])
        if not isinstance(item.get("statement"), str) or not 1 <= len(item["statement"]) <= 1000:
            raise TrackerError("An assumption needs a statement of 1 to 1000 characters")
        terms = item.get("terms")
        if not isinstance(terms, list) or not terms or len(terms) > 20 or any(not isinstance(t, str) or not 2 <= len(t.strip()) <= 100 for t in terms):
            raise TrackerError("Each assumption needs 1 to 20 search terms of 2 to 100 characters")
        if item.get("priority", "medium") not in {"high", "medium", "low"}:
            raise TrackerError("Assumption priority must be high, medium, or low")
    return items


def link_assumptions(change, assumptions):
    if change["kind"] == "unchanged":
        return []
    text = " ".join(change[s]["text"] for s in ("old", "new") if change[s]).lower()
    links = []
    for item in assumptions:
        matched = [term for term in item["terms"] if re.search(r"(?<!\w)" + re.escape(term.lower().strip()) + r"(?!\w)", text)]
        if matched:
            links.append({"id": item["id"], "statement": item["statement"], "terms": matched,
                          "priority": item.get("priority", "medium"),
                          "interpretation": "Keyword relevance only; analyst must decide whether this supports or challenges the assumption."})
    return links
