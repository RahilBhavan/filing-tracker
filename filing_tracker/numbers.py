"""Conservative narrative quantities with explicit units and period provenance."""

import re
from collections import defaultdict
from decimal import Decimal

AMOUNT = re.compile(r"(?P<currency>\$|USD\s+|EUR\s+|€|GBP\s+|£)?\s*(?P<number>\(?[+-]?\d[\d,]*(?:\.\d+)?\)?)\s*(?P<scale>billion|million|thousand)?\s*(?P<unit>%|percent\b|shares\b)?", re.I)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
METRICS = [
    (r"microsoft cloud(?: \(formerly commercial cloud\))? revenue", "Microsoft Cloud revenue"),
    (r"effective tax rate", "effective tax rate"),
    (r"gross margin", "gross margin"),
    (r"operating income", "operating income"),
    (r"operating expenses", "operating expenses"),
    (r"cash(?:, cash equivalents,? and short.term investments| and equivalents)", "cash and investments"),
    (r"(?:capital spending|capital expenditures)", "capital spending"),
    (r"largest supplier", "supplier concentration"),
    (r"(?:repurchased|repurchase)", "share repurchases"),
    (r"net revenue|total revenue|revenue", "revenue"),
    (r"net sales", "net sales"),
]


def metric_mentions(text):
    """Specific phrases win over overlapping generic names, never over other metrics."""
    found = []
    for pattern, label in METRICS:
        for match in re.finditer(pattern, text, re.I):
            if not any(match.start() < end and match.end() > start for start, end, _ in found):
                found.append((match.start(), match.end(), label))
    return sorted(found)


def year_matches(text):
    quantities = [m for m in AMOUNT.finditer(text) if m['currency'] or m['unit'] or m['scale']]
    return [m for m in YEAR.finditer(text)
            if not any(q.start() <= m.start() < q.end() for q in quantities)]


def date_only_change(old, new):
    if old == new:
        return False
    # Full dates and years are suppressed only if all other text is unchanged.
    date = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(?:19|20)\d{2}\b", re.I)
    def scrub(text):
        text = date.sub("<date>", text)
        for match in reversed(year_matches(text)):
            # Bare quantities such as "2023 employees" are not calendar years.
            prefix = text[max(0, match.start() - 30):match.start()]
            if not (re.search(r"(?:fiscal|year|in|during|for|since|through|ended)\s*$", prefix, re.I)
                    or text.strip() == match.group()):
                continue
            text = text[:match.start()] + "<year>" + text[match.end():]
        return text
    return scrub(old) == scrub(new)


def extract_facts(text, fiscal_year):
    facts = []
    sentences = re.split(r"(?<=[.;])\s+(?=[A-Z])", text)
    offset = 0
    for sentence in sentences:
        start = text.find(sentence, offset)
        offset = start + len(sentence)
        mentions = metric_mentions(sentence)
        if not mentions or len({m[2] for m in mentions}) != 1:
            continue  # Multiple metrics require clause-level attribution; abstain.
        metric_start, _, metric = mentions[0]
        duration = "quarter" if re.search(r"quarter|three months", sentence, re.I) else "ytd" if re.search(r"six months|nine months|year.to.date", sentence, re.I) else "annual"
        candidates = []
        for match in AMOUNT.finditer(sentence):
            if not (match["currency"] or match["unit"] or match["scale"]):
                continue
            if not match["currency"] and not match["unit"]:
                continue  # "12 million" without a currency or named unit is ambiguous.
            value = Decimal(match["number"].replace(",", "").strip("()"))
            if match["number"].startswith("("):
                value = -value
            scale = {"thousand": 1000, "million": 10**6, "billion": 10**9}.get((match["scale"] or "").lower(), 1)
            unit = "percent" if (match["unit"] or "").lower() in {"%", "percent"} else "shares" if match["unit"] else {"€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}.get((match["currency"] or "").strip(), "USD")
            if metric in {"effective tax rate", "supplier concentration"} and unit != "percent":
                continue
            if unit != "percent":
                value *= scale
            prefix = sentence[max(metric_start, match.start() - 35):match.start()].lower().strip()
            role = "reported level"
            direction = re.search(r"(increased|decreased|grew|declined|fell|growth of)(?:\s+by)?\s*$", prefix)
            if direction:
                role = "reported growth rate" if unit == "percent" else "reported change amount"
                if direction[1] in {"decreased", "declined", "fell"}:
                    value = -abs(value)
            if metric == "share repurchases":
                role = "shares bought" if unit == "shares" else "repurchase spending"
            candidates.append({"metric": metric, "value": float(value), "unit": unit, "role": role,
                               "duration": duration, "start": start + match.start(), "end": start + match.end(),
                               "raw": match.group().strip(), "_start": match.start(), "_end": match.end()})
        years = [int(y.group()) for y in year_matches(sentence)]
        grouped = defaultdict(list)
        for fact in candidates:
            grouped[(fact["metric"], fact["unit"], fact["role"])].append(fact)
        for group in grouped.values():
            respectively = "respectively" in sentence.lower() and len(years) == len(group) and len(set(years)) == len(years)
            for i, fact in enumerate(group):
                tail = sentence[fact["_end"]:]
                direct = re.match(r"\s+(?:for|in|during)\s+(?:fiscal\s+)?(?:year\s+)?((?:19|20)\d{2})\b", tail, re.I)
                if direct:
                    fact["period"], fact["period_basis"] = int(direct[1]), "explicit adjoining year"
                elif respectively:
                    fact["period"], fact["period_basis"] = years[i], "explicit ordered years and respectively"
                elif len(set(years)) == 1:
                    fact["period"], fact["period_basis"] = years[0], "single year in sentence"
                elif years:
                    fact["period"], fact["period_basis"] = None, "ambiguous multiple years"
                else:
                    fact["period"], fact["period_basis"] = fiscal_year, "document fiscal year inferred; verify context"
                if re.search(r"next year|forecast|outlook|anticipates|expect", sentence, re.I):
                    fact["duration"] = "forecast"
                    fact["period_basis"] = "forecast timing not resolved"
                    fact["period"] = None
                del fact["_start"], fact["_end"]
                facts.append(fact)
    return facts


def compare_numbers(old, new, old_year, new_year):
    if date_only_change(old, new):
        return {"date_only": True, "comparisons": [], "abstentions": ["Only a date or year changed"], "old_facts": [], "new_facts": []}
    before, after = extract_facts(old, old_year), extract_facts(new, new_year)
    groups = []
    for facts in (before, after):
        group = defaultdict(list)
        for fact in facts:
            group[(fact["metric"], fact["unit"], fact["role"], fact["duration"])].append(fact)
        groups.append(group)
    comparisons, abstentions = [], []
    if any(len({m[2] for m in metric_mentions(sentence)}) > 1
           for text in (old, new) for sentence in re.split(r"(?<=[.;])\s+(?=[A-Z])", text)):
        abstentions.append("Multiple metrics in one sentence; quantity attribution is ambiguous; no arithmetic for that sentence")
    for key in sorted(set(groups[0]) | set(groups[1])):
        left, right = groups[0].get(key, []), groups[1].get(key, [])
        if not left or not right:
            abstentions.append("%s: no matched metric, role, unit, and duration on both sides" % key[0])
            continue
        if any(f["period"] is None for f in left + right) or key[3] in {"forecast", "quarter", "ytd"}:
            abstentions.append("%s: unresolved timing or nonannual duration; no arithmetic" % key[0])
            continue
        old_latest, new_latest = max(f["period"] for f in left), max(f["period"] for f in right)
        a, b = [f for f in left if f["period"] == old_latest], [f for f in right if f["period"] == new_latest]
        if len(a) != 1 or len(b) != 1 or new_latest - old_latest not in {0, 1}:
            abstentions.append("%s: duplicate quantities or nonadjacent periods; no arithmetic" % key[0])
            continue
        a, b = a[0], b[0]
        delta = b["value"] - a["value"]
        comparisons.append({"metric": key[0], "unit": key[1], "role": key[2], "old": a, "new": b,
            "absolute_change": round(delta, 8), "percentage_point_change": round(delta, 8) if key[1] == "percent" else None,
            "relative_change_percent": round(delta / a["value"] * 100, 6) if a["value"] > 0 and key[1] != "percent" else None,
            "basis": "same-period reported value change" if old_latest == new_latest else "successive annual reported quantities",
            "caution": "Verify constant metric definition and scope; no currency conversion or restatement inference."})
    if not before and not after and re.search(r"\d", old + new):
        abstentions.append("No supported, explicitly unit-qualified narrative metric; tables and bare numbers need review")
    return {"date_only": False, "comparisons": comparisons, "abstentions": abstentions, "old_facts": before, "new_facts": after}
