"""Write source snapshots and reports with locally verifiable citations."""

import csv
import html
import json
import shutil
from collections import Counter
from pathlib import Path

from .core import SECTIONS, TrackerError


def source_blocks(block):
    return block.get("members", [block]) if block else []


def md(text):
    text = html.escape(str(text), quote=False)
    for char in "\\`*_{}[]()#+!|":
        text = text.replace(char, "\\" + char)
    return text.replace("\n", " ")


def citation(result, change, side):
    block = change[side]
    if block is None:
        return ""
    return "sources/%s.html#%s" % (result[side]["id"], source_blocks(block)[0]["id"])


def safe_csv(value):
    # Protect spreadsheet users from formula execution in source text and notes.
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def write_report(pair, result, out):
    out = Path(out).resolve()
    # Overwriting a manifest or a source makes reproducibility impossible.
    for doc in (pair["old"], pair["new"]):
        raw = Path(doc["raw_path"])
        if out == raw.parent or out in raw.parents:
            raise TrackerError("Report directory must not contain source documents")
    out.mkdir(parents=True, exist_ok=True)
    # A new comparison invalidates metrics from any previous evaluation here.
    if (out / "metrics.json").exists():
        (out / "metrics.json").unlink()
    sources = out / "sources"
    sources.mkdir(exist_ok=True)
    synthetic = result["provenance"] == "synthetic"
    banner = "SYNTHETIC FIXTURE — fictional company and disclosures; not SEC evidence." if synthetic else "ISSUER-HOSTED FILING — converted text; check the preserved original document." if result["provenance"] == "issuer" else "SEC source — verify each extracted passage against the original filing."
    for side in ("old", "new"):
        doc = pair[side]
        meta = doc["metadata"]
        shutil.copyfile(doc["raw_path"], sources / (meta["id"] + ".original.html"))
        original_name = meta["id"] + ".original.html"
        if doc.get("original_path"):
            original = Path(doc["original_path"])
            original_name = meta["id"] + ".original" + original.suffix
            shutil.copyfile(original, sources / original_name)
        (sources / (meta["id"] + ".txt")).write_text(doc["text"], encoding="utf-8")
        title = "%s — FY %s" % (meta["company"], meta["fiscal_year"])
        parts = ['<!doctype html><html lang="en"><meta charset="utf-8">',
                 "<title>%s</title>" % html.escape(title),
                 "<style>body{max-width:900px;margin:40px auto;padding:0 20px;font:17px/1.6 system-ui}article{border-top:1px solid #bbb;padding:15px 0}article:target{background:#fff4b8}pre{white-space:pre-wrap}small{color:#444}</style>",
                 "<h1>%s</h1><p><strong>%s</strong></p>" % (html.escape(title), html.escape(banner)),
                 "<p>Accession: %s. Period ended %s. Filed %s.</p>" % tuple(html.escape(str(meta[k])) for k in ("accession", "period_end", "filed")),
                 '<p>Original SHA-256: <code>%s</code>. <a href="%s.original.html">Original HTML</a> · <a href="%s.txt">Normalized text</a></p>' % (meta["sha256"], meta["id"], meta["id"])]
        if meta.get("source_url"):
            parts.append('<p><a href="%s">Publisher original</a> · <a href="%s">Preserved original file</a></p>' % (html.escape(meta["source_url"], quote=True), original_name))
            if meta.get("original_sha256"):
                parts.append("<p>Original file SHA-256: <code>%s</code>. The HTML above is a converted view.</p>" % meta["original_sha256"])
        for block in doc["blocks"]:
            parts.append('<article id="%s"><h2>%s · %s</h2><small>Normalized character offsets [%d, %d). Original DOM id: %s</small><p>%s</p></article>' %
                         (block["id"], html.escape(SECTIONS[block["section"]]), block["id"], block["start"], block["end"], html.escape(block["dom_id"] or "none"), html.escape(block["text"])))
            if block.get("source_locator"):
                suffix = "#page=%d" % block["page"] if block.get("page") else ""
                parts.append('<p><a href="%s%s">%s</a></p>' % (original_name, suffix, html.escape(block["source_locator"])))
        parts.append("</html>")
        (sources / (meta["id"] + ".html")).write_text("\n".join(parts), encoding="utf-8")
    result["counts"] = dict(Counter(c["kind"] for c in result["changes"]))
    for change in result["changes"]:
        change["old_citation"] = citation(result, change, "old")
        change["new_citation"] = citation(result, change, "new")
        for side in ("old", "new"):
            change[side + "_citations"] = ["sources/%s.html#%s" % (result[side]["id"], b["id"]) for b in source_blocks(change[side])]
    (out / "comparison.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "applied_review" in result:
        (out / "applied-review.json").write_text(json.dumps(result["applied_review"], indent=2) + "\n", encoding="utf-8")
    template = {"pair_fingerprint": pair["fingerprint"], "alignments": [], "reviews": {}}
    # Do not destroy a user's edited review template on rerun.
    if not (out / "review.json").exists():
        (out / "review.json").write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    fields = ["id", "section", "kind", "priority", "score", "status", "ambiguous_alignment", "moved", "old_block", "new_block", "old_text", "new_text", "old_citation", "new_citation", "old_citations", "new_citations", "reasons", "review_note", "numeric_comparisons", "assumptions", "provenance"]
    with (out / "changes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for change in result["changes"]:
            row = {k: change[k] for k in fields if k in change}
            row.update({"old_block": change["old"]["id"] if change["old"] else "",
                        "new_block": change["new"]["id"] if change["new"] else "",
                        "old_text": change["old"]["text"] if change["old"] else "",
                        "new_text": change["new"]["text"] if change["new"] else "",
                        "reasons": "; ".join(change["reasons"]), "provenance": result["provenance"],
                        "old_citations": "; ".join(change["old_citations"]), "new_citations": "; ".join(change["new_citations"]),
                        "numeric_comparisons": json.dumps(change.get("numeric", {}).get("comparisons", [])),
                        "assumptions": "; ".join(a["id"] for a in change.get("assumption_links", []))})
            writer.writerow({k: safe_csv(v) for k, v in row.items()})
    lines = ["# Filing change review", "", banner, "", "Rule-based draft. Review priority is a reading order, not a materiality determination.", ""]
    for side in ("old", "new"):
        meta = result[side]
        lines += ["%s: %s, CIK %s, %s, FY %s, period end %s, filed %s, accession %s. [Source snapshot](sources/%s.html)." %
                  (side.title(), md(meta["company"]), md(meta["cik"]), meta["form"], meta["fiscal_year"], meta["period_end"], meta["filed"], md(meta["accession"]), meta["id"]), ""]
    lines += ["Counts: " + ", ".join("%s=%s" % (k, v) for k, v in sorted(result["counts"].items())), "",
              "Full excerpts and all unchanged matches are in changes.csv and comparison.json. Omitted passages mean unmatched text in the selected section, not proof that a disclosure disappeared from the entire filing.", ""]
    lines += ["| Section | Old blocks | New blocks |", "| --- | --- | --- |"]
    for section in result["sections"].values():
        lines.append("| %s | %d | %d |" % (md(section["label"]), section["old_blocks"], section["new_blocks"]))
    lines.append("")
    if result.get("assumptions"):
        lines += ["## Analyst assumptions", "", "Analyst-authored hypotheses. Keyword links do not establish support or contradiction.", ""]
        for assumption in result["assumptions"]:
            lines += ["- %s: %s" % (md(assumption["id"]), md(assumption["statement"]))]
        lines.append("")
    for warning in result["warnings"]:
        lines += ["Parser warning: " + md(warning), ""]
    for change in result["changes"]:
        if change["kind"] == "unchanged":
            continue
        lines += ["## %s · %s · %s · %s" % (change["id"], change["kind"], change["priority"], change["status"]), "",
                  "Observed text comparison in %s. Alignment: %s%s." % (md(SECTIONS[change["section"]]), change["method"], "; uncertain match" if change["ambiguous_alignment"] else ""), ""]
        for side in ("old", "new"):
            if change[side]:
                for block, link in zip(source_blocks(change[side]), change[side + "_citations"]):
                    lines += ["%s ([source](%s)): %s" % (side.title(), link, md(block["text"])), ""]
            else:
                lines += ["%s: no matched passage in this section." % side.title(), ""]
        lines += ["Review rule: " + md("; ".join(change["reasons"])) + ".", "",
                  "Analyst interpretation: " + (md(change["review_note"]) + " [reviewer-supplied]" if change["review_note"] else "Pending. No investment conclusion generated."), ""]
        for quantity in change.get("numeric", {}).get("comparisons", []):
            lines += ["Calculated from the cited passages: %s, %s, %s %s in %s to %s in %s. Absolute change %s%s. %s" %
                      (md(quantity["metric"]), md(quantity["role"]), quantity["old"]["value"], quantity["unit"], quantity["old"]["period"], quantity["new"]["value"], quantity["new"]["period"], quantity["absolute_change"], " percentage points" if quantity["unit"] == "percent" else " " + quantity["unit"], md(quantity["caution"])), ""]
        for assumption in change.get("assumption_links", []):
            lines += ["Related assumption %s: %s. Matched terms: %s. Analyst assessment pending." % (md(assumption["id"]), md(assumption["statement"]), md(", ".join(assumption["terms"]))), ""]
        if change["status"] == "dismissed":
            lines += ["Reviewer dismissed this item; preserved here for the audit trail.", ""]
    (out / "memo.md").write_text("\n".join(lines), encoding="utf-8")
    return out
