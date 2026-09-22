"""Context-aware, deterministic section matching with adjacent split/merge support."""

import copy
import re

from .core import (SECTIONS, TrackerError, digest, make_change, normalize, similarity)
from .numbers import compare_numbers
from .thesis import link_assumptions, validate_assumptions

STOP = set("a an and as at be been by can could for from have has in into is it its may of on or our that the their these this to was we were which will with would you your".split())


def terms(text):
    return {t for t in re.findall(r"[a-z]{3,}", text.lower()) if t not in STOP}


def members(block):
    return block.get("members", [block]) if block else []


def combine(blocks):
    if not blocks:
        return None
    if len(blocks) == 1:
        return blocks[0]
    result = dict(blocks[0])
    result.update({"members": blocks, "text": "\n\n".join(b["text"] for b in blocks),
                   "end": blocks[-1]["end"], "id": "+".join(b["id"] for b in blocks)})
    return result


def ids(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return value
    raise TrackerError("Alignment sides must be block IDs, lists of IDs, or null")


def validate_group(identifiers, mapping, used):
    if len(identifiers) != len(set(identifiers)) or any(x not in mapping or x in used for x in identifiers):
        raise TrackerError("Invalid or reused block in alignment override")
    blocks = [mapping[x] for x in identifiers]
    if blocks and (len({b["section"] for b in blocks}) > 1 or any(b["index"] != blocks[0]["index"] + i for i, b in enumerate(blocks))):
        raise TrackerError("Grouped blocks must be consecutive within one section")
    return blocks


def build_change(old_blocks, new_blocks, method, score=None, ambiguous=False):
    old, new = combine(old_blocks), combine(new_blocks)
    change = make_change((old or new)["section"], old, new, method, score, ambiguous)
    if old and new and normalize(old["text"]) == normalize(new["text"]):
        change.update(kind="unchanged", score=0, priority="low", status="unchanged", needs_review=False,
                      reasons=["Same text after whitespace normalization; paragraph grouping may differ"])
    return change


def contextual_matches(olds, news, anchors, threshold):
    candidates = []
    wordsets = {b["id"]: terms(b["text"]) for b in news}
    for old in olds:
        old_terms = terms(old["text"])
        choices = []
        for new in news:
            if (old.get("kind") == "heading") != (new.get("kind") == "heading"):
                continue
            union = old_terms | wordsets[new["id"]]
            overlap = len(old_terms & wordsets[new["id"]]) / max(1, len(union))
            if overlap >= 0.08:
                choices.append((overlap, new))
        for overlap, new in sorted(choices, key=lambda x: (-x[0], x[1]["id"]))[:8]:
            base = similarity(old["text"], new["text"])
            # A stable, distinctive lead under the same heading can survive a rewritten explanation.
            old_lead = re.split(r"(?<=[.!?])\s+", old["text"], maxsplit=1)[0]
            new_lead = re.split(r"(?<=[.!?])\s+", new["text"], maxsplit=1)[0]
            mask = lambda text: re.sub(r"\d[\d,.]*", "#", text.lower())
            same_heading = bool(old.get("subsection") and old.get("subsection") == new.get("subsection"))
            stable_lead = (same_heading and len(terms(old_lead)) >= 5
                           and similarity(mask(old_lead), mask(new_lead)) >= 0.9)
            nearby_anchor = any(anchors.get(old["index"] + d) == new["index"] + d for d in (-1, 1))
            expanded_heading = (old.get("kind") == new.get("kind") == "heading"
                and nearby_anchor and min(len(terms(old["text"])), len(terms(new["text"]))) >= 2
                and (new["text"].lower().startswith(old["text"].lower().rstrip("."))
                     or old["text"].lower().startswith(new["text"].lower().rstrip("."))))
            if base < 0.45 and not (stable_lead or expanded_heading):
                continue
            boost = 0.0
            a, b = old.get("subsection", ""), new.get("subsection", "")
            if a and b:
                heading_score = similarity(a, b)
                if heading_score > 0.8:
                    boost += 0.08
                elif heading_score < 0.3:
                    boost -= 0.08
            for direction in (-1, 1):
                known = anchors.get(old["index"] + direction)
                if known is not None and 0 < (known - new["index"]) * direction <= 3:
                    boost += 0.04
            score = min(1.0, max(base + boost, 0.66 if stable_lead or expanded_heading else 0))
            if score >= threshold:
                candidates.append((score, old, new, base))
    return candidates


def compare_v2(pair, review=None, threshold=0.62, assumptions=None):
    if not 0 < threshold <= 1:
        raise TrackerError("Alignment threshold must be in (0, 1]")
    review = review or {}
    if not isinstance(review, dict) or set(review) - {"pair_fingerprint", "alignments", "reviews"}:
        raise TrackerError("Review must contain only pair_fingerprint, alignments, and reviews")
    if review and review.get("pair_fingerprint") != pair["fingerprint"]:
        raise TrackerError("Review file belongs to a different source pair")
    if not isinstance(review.get("alignments", []), list) or not isinstance(review.get("reviews", {}), dict):
        raise TrackerError("Invalid review lists or objects")
    assumptions = validate_assumptions(assumptions)
    maps = {side: {b["id"]: b for b in pair[side]["blocks"]} for side in ("old", "new")}
    used = {"old": set(), "new": set()}
    changes = []

    def add(old, new, method, score=None, ambiguous=False):
        changes.append(build_change(old, new, method, score, ambiguous))
        used["old"].update(b["id"] for b in old)
        used["new"].update(b["id"] for b in new)

    for override in review.get("alignments", []):
        if not isinstance(override, dict) or set(override) != {"old", "new"}:
            raise TrackerError("Each alignment must specify old and new")
        old = validate_group(ids(override["old"]), maps["old"], used["old"])
        new = validate_group(ids(override["new"]), maps["new"], used["new"])
        if not old and not new:
            raise TrackerError("An alignment cannot have two empty sides")
        if old and new and old[0]["section"] != new[0]["section"]:
            raise TrackerError("Cross-section alignment is unsupported")
        add(old, new, "reviewer")

    for section in SECTIONS:
        olds = [b for b in maps["old"].values() if b["section"] == section]
        news = [b for b in maps["new"].values() if b["section"] == section]
        anchors = {}
        for old in olds:
            if old["id"] in used["old"]:
                continue
            matches = [b for b in news if b["id"] not in used["new"] and b["text"] == old["text"]]
            if matches:
                new = min(matches, key=lambda b: (abs(b["index"] - old["index"]), b["id"]))
                add([old], [new], "exact", 1.0)
                anchors[old["index"]] = new["index"]
        remaining = lambda side, blocks: [b for b in blocks if b["id"] not in used[side]]
        # Group only adjacent non-heading blocks, and require a clear gain over single matching.
        group_candidates = []
        for flip in (False, True):
            left, right = (remaining("new", news), remaining("old", olds)) if flip else (remaining("old", olds), remaining("new", news))
            for single in left:
                if single.get("kind") in {"heading", "table_row"}:
                    continue
                single_terms = terms(single["text"])
                for i in range(len(right) - 1):
                    group = right[i:i + 2]
                    if group[1]["index"] != group[0]["index"] + 1 or any(b.get("kind") in {"heading", "table_row"} for b in group):
                        continue
                    if group[0].get("subsection") != group[1].get("subsection"):
                        continue
                    joined = normalize(" ".join(b["text"] for b in group))
                    if abs(len(joined) - len(single["text"])) > max(len(joined), len(single["text"])) * 0.35:
                        continue
                    if len(single_terms & terms(joined)) / max(1, len(single_terms | terms(joined))) < 0.35:
                        continue
                    score = similarity(single["text"], joined)
                    if score >= max(0.82, threshold) and score - max(similarity(single["text"], b["text"]) for b in group) >= 0.09:
                        group_candidates.append((score, group if flip else [single], [single] if flip else group))
        for score, old, new in sorted(group_candidates, key=lambda x: (-x[0], x[1][0]["id"], x[2][0]["id"])):
            if any(b["id"] in used["old"] for b in old) or any(b["id"] in used["new"] for b in new):
                continue
            add(old, new, "adjacent-group", score, True)
        candidates = contextual_matches(remaining("old", olds), remaining("new", news), anchors, threshold)
        for score, old, new, base in sorted(candidates, key=lambda x: (-x[0], x[1]["id"], x[2]["id"])):
            if old["id"] in used["old"] or new["id"] in used["new"]:
                continue
            close = any((a["id"] == old["id"] or b["id"] == new["id"]) and (a["id"], b["id"]) != (old["id"], new["id"]) and abs(score - s) < 0.04 for s, a, b, _ in candidates)
            add([old], [new], "contextual", score, base < 0.75 or close)
        for old in remaining("old", olds):
            add([old], [], "unmatched", ambiguous=True)
        for new in remaining("new", news):
            add([], [new], "unmatched", ambiguous=True)

    for change in changes:
        before = change["old"]["text"] if change["old"] else ""
        after = change["new"]["text"] if change["new"] else ""
        numeric = compare_numbers(before, after, pair["old"]["metadata"].get("fiscal_year", 0), pair["new"]["metadata"].get("fiscal_year", 1))
        change["numeric"] = numeric
        change["assumption_links"] = link_assumptions(change, assumptions)
        if change["kind"] != "unchanged":
            if numeric["date_only"]:
                change["score"] = 5
                change["reasons"] = ["Date/year-only rollover; all other text unchanged"]
            for quantity in numeric["comparisons"]:
                if quantity["metric"] == "supplier concentration" and abs(quantity["absolute_change"]) >= 10:
                    change["score"] = max(change["score"], 88)
                    change["reasons"].append("Supplier concentration changed at least 10 percentage points")
            if re.search(r"suspend\w*|terminat\w*", after, re.I) and re.search(r"repurchase|buyback|agreement", after, re.I):
                change["score"] = max(change["score"], 88)
                change["reasons"].append("Suspension or termination language affects capital return or a contract")
            if change["assumption_links"] and not numeric["date_only"]:
                importance = max({"low": 5, "medium": 10, "high": 15}[x["priority"]] for x in change["assumption_links"])
                change["score"] = min(99, change["score"] + importance)
                change["reasons"].append("Matches an analyst assumption; keyword relevance needs interpretation")
            change["priority"] = "high" if change["score"] >= 75 else "medium" if change["score"] >= 50 else "low"
    by_id = {c["id"]: c for c in changes}
    for identifier, decision in review.get("reviews", {}).items():
        if identifier not in by_id:
            raise TrackerError("Review references a change absent after alignment: " + identifier)
        if not isinstance(decision, dict) or set(decision) - {"priority", "status", "note"}:
            raise TrackerError("Invalid review decision")
        c = by_id[identifier]
        if "priority" in decision:
            if decision["priority"] not in {"high", "medium", "low"}:
                raise TrackerError("Invalid reviewer priority")
            c["priority"] = decision["priority"]
            c["score"] = {"high": 100, "medium": 55, "low": 10}[decision["priority"]]
            c["reasons"].append("Priority set by reviewer")
        if "status" in decision:
            if decision["status"] not in {"accepted", "dismissed", "needs_review"}:
                raise TrackerError("Invalid review status")
            c["status"] = decision["status"]
            c["needs_review"] = decision["status"] == "needs_review"
        if "note" in decision:
            if not isinstance(decision["note"], str) or len(decision["note"]) > 5000:
                raise TrackerError("Review note must be text up to 5000 characters")
            c["review_note"] = decision["note"]
    changes.sort(key=lambda c: (c["status"] == "dismissed", -c["score"], c["section"], c["id"]))
    return {"schema_version": 2, "engine": "v2", "pair_fingerprint": pair["fingerprint"],
            "provenance": pair["manifest"]["provenance"], "threshold": threshold,
            "old": pair["old"]["metadata"], "new": pair["new"]["metadata"],
            "assumptions": assumptions, "applied_review": copy.deepcopy(review),
            "sections": {s: {"label": label, "old_blocks": sum(b["section"] == s for b in maps["old"].values()), "new_blocks": sum(b["section"] == s for b in maps["new"].values())} for s, label in SECTIONS.items()},
            "warnings": pair["old"]["warnings"] + pair["new"]["warnings"], "changes": changes}
