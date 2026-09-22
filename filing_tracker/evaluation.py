"""Evaluate exact block-pair decisions against separately authored gold labels."""

import json
from pathlib import Path

from .core import TrackerError, compare, load_pair
from .report import write_report


def fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": round(numerator / denominator, 4) if denominator else None}


def key(change):
    return (change["old"]["dom_id"] if change["old"] else None,
            change["new"]["dom_id"] if change["new"] else None, change["kind"])


def evaluate(manifest, gold_path, out):
    pair = load_pair(manifest)
    result = compare(pair)
    gold = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    if gold["pair_fingerprint"] != pair["fingerprint"]:
        raise TrackerError("Gold labels do not match this source pair")
    labels = gold["labels"]
    expected = {(x["old"], x["new"], x["kind"]): x for x in labels}
    if len(expected) != len(labels):
        raise TrackerError("Duplicate gold decision")
    for side in ("old", "new"):
        identifiers = [b["dom_id"] for b in pair[side]["blocks"]]
        if None in identifiers or len(identifiers) != len(set(identifiers)):
            raise TrackerError("Gold evaluation requires unique, nonempty DOM IDs on source blocks")
        covered = [row[side] for row in labels if row[side] is not None]
        if len(covered) != len(set(covered)) or set(identifiers) != set(covered):
            raise TrackerError("Gold labels must cover each parsed %s block exactly once" % side)
    write_report(pair, result, out)
    actual = {key(c) for c in result["changes"]}
    predicted_changes = {k for k in actual if k[2] != "unchanged"}
    true_changes = {k for k in expected if k[2] != "unchanged"}
    true_positive = len(predicted_changes & true_changes)
    ranked = [c for c in result["changes"] if c["kind"] != "unchanged"]
    high = {k for k, value in expected.items() if value["importance"] == 2 and k[2] != "unchanged"}
    metrics = {
        "label_count": len(labels), "gold_changes": len(true_changes), "predicted_changes": len(predicted_changes),
        "true_positive": true_positive, "false_positive": len(predicted_changes - true_changes),
        "false_negative": len(true_changes - predicted_changes),
        "precision": fraction(true_positive, len(predicted_changes)),
        "recall": fraction(true_positive, len(true_changes)),
        "alignment_and_type_accuracy": fraction(len(actual & expected.keys()), len(expected)),
        "high_priority_recall_at_10": fraction(len(high & {key(c) for c in ranked[:10]}), len(high)),
    }
    for k in (5, 10):
        items = ranked[:k]
        relevant = sum(expected.get(key(c), {}).get("importance", 0) >= 1 for c in items)
        metrics["precision_at_%d" % k] = fraction(relevant, len(items))
    citation_count = valid_citations = 0
    for change in result["changes"]:
        for side in ("old", "new"):
            block = change[side]
            if block:
                citation_count += 1
                target, anchor = change[side + "_citation"].split("#")
                source = Path(out) / target
                text = pair[side]["text"]
                valid = text[block["start"]:block["end"]] == block["text"]
                valid = valid and source.exists() and ('id="%s"' % anchor) in source.read_text(encoding="utf-8")
                valid_citations += int(valid)
    metrics["local_citation_integrity"] = fraction(valid_citations, citation_count)
    metrics["missed_gold_decisions"] = [list(k) for k in expected if k not in actual]
    metrics["unexpected_predictions"] = [list(k) for k in sorted(actual - expected.keys(), key=str)]
    metrics["scope"] = "Synthetic, author-labeled block decisions. No real SEC accuracy, finance-expert importance validation, or time savings measured."
    Path(out, "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics
