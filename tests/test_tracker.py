import copy
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from filing_tracker.__main__ import main
from filing_tracker.core import (TrackerError, compare, digest, edit_spans, load_pair,
                                 parse_html, rank_change, similarity)
from filing_tracker.evaluation import evaluate
from filing_tracker.report import safe_csv, write_report
from filing_tracker.sec import SECClient, fetch_pair


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def fixture(name="development"):
    return load_pair(FIXTURES / (name + "-pair.json"))


def simple_pair(old, new):
    def blocks(texts):
        return [{"id": "risk-%04d" % i, "index": i, "section": "risk", "text": text,
                 "dom_id": str(i), "start": 0, "end": len(text)} for i, text in enumerate(texts, 1)]
    return {"fingerprint": "test-pair", "manifest": {"provenance": "synthetic"},
            "old": {"metadata": {}, "blocks": blocks(old), "warnings": []},
            "new": {"metadata": {}, "blocks": blocks(new), "warnings": []}}


class ParserTests(unittest.TestCase):
    def test_fixture_sections_exclude_toc_hidden_and_other_items(self):
        pair = fixture()
        self.assertEqual(len(pair["old"]["blocks"]), 16)
        text = pair["old"]["text"]
        for unwanted in ("must be ignored", "Excluded", "Outside MVP", "Hidden metadata"):
            self.assertNotIn(unwanted, text)
        self.assertEqual({b["section"] for b in pair["old"]["blocks"]}, {"risk", "mda"})

    def test_inline_xbrl_number_table_units_and_offsets(self):
        doc = fixture()["new"]
        row = next(b for b in doc["blocks"] if b["dom_id"] == "table")
        self.assertEqual(row["text"], "Cash and equivalents | $9 million")
        self.assertEqual(row["kind"], "table_row")
        for block in doc["blocks"]:
            self.assertEqual(doc["text"][block["start"]:block["end"]], block["text"])

    def test_missing_section_fails(self):
        with self.assertRaisesRegex(TrackerError, "Missing or empty"):
            parse_html("<h2>Item 1A. Risk Factors</h2><p>Only risk.</p>")

    def test_nested_hidden_elements_and_scripts_do_not_leak(self):
        raw = '<h2>Item 1A. Risk Factors</h2><p>May <span hidden><b>NOT SECRET</b></span> reduce demand.</p><script>FAKE</script><h2>Item 1B. Other</h2><h2>Item 7. Management Discussion</h2><p>Cash is $10 million.</p><h2>Item 7A. Market risk</h2>'
        blocks, text, _ = parse_html(raw)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("FAKE", text)
        self.assertEqual(blocks[0]["text"], "May reduce demand.")

    def test_largest_section_beats_table_of_contents_candidate(self):
        raw = '<p>Item 1A. Risk Factors</p><p>page 5</p><p>Item 1B. Other</p><p>Item 7. Management Discussion</p><p>page 12</p><p>Item 7A. Other</p><h2>Item 1A. Risk Factors</h2><p>Real risk disclosure with enough text.</p><h2>Item 1B. Other</h2><h2>Item 7. Management Discussion</h2><p>Real management discussion with numbers $10.</p><h2>Item 8. Statements</h2>'
        blocks, text, warnings = parse_html(raw)
        self.assertEqual(len(blocks), 2)
        self.assertNotIn("page 5", text)
        self.assertEqual(len(warnings), 2)

    def test_running_page_headers_continue_the_section(self):
        blocks, text, warnings = parse_html((FIXTURES / "page-headers.html").read_text(encoding="utf-8"))
        risk = [b["text"] for b in blocks if b["section"] == "risk"]
        self.assertEqual(len(risk), 3)
        self.assertIn("First page", risk[0])
        self.assertIn("Third page", risk[2])
        self.assertEqual(len([b for b in blocks if b["section"] == "mda"]), 2)
        for furniture in ("22", "PART I", "PART II"):
            self.assertNotIn(furniture + "\n", text)
        self.assertEqual(warnings, [])


class AlignmentTests(unittest.TestCase):
    def test_reordering_is_unchanged_and_one_to_one(self):
        pair = simple_pair(["Alpha remains strong.", "Beta remains stable."], ["Beta remains stable.", "Alpha remains strong."])
        changes = compare(pair)["changes"]
        self.assertEqual([c["kind"] for c in changes], ["unchanged", "unchanged"])
        self.assertTrue(all(c["moved"] for c in changes))

    def test_duplicate_exact_text_does_not_reuse_block(self):
        changes = compare(simple_pair(["Repeated disclosure."] * 2, ["Repeated disclosure."]))["changes"]
        self.assertEqual(sorted(c["kind"] for c in changes), ["removed", "unchanged"])
        self.assertEqual(sum(c["new"] is not None for c in changes), 1)

    def test_numeric_rollover_aligns(self):
        before = "Net revenue was $120 million for 2023, compared with $110 million for 2022."
        after = "Net revenue was $135 million for 2024, compared with $120 million for 2023."
        changes = compare(simple_pair([before], [after]))["changes"]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["kind"], "changed")
        self.assertGreaterEqual(similarity(before, after), 0.62)

    def test_negation_minimal_edit_and_rank(self):
        before, after = "We are not in compliance.", "We are in compliance."
        spans = edit_spans(before, after)
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["old"]["text"], "not")
        self.assertEqual(spans[0]["new"]["text"], "")
        score, reasons = rank_change("changed", "mda", before, after)
        self.assertEqual(score, 85)
        self.assertIn("Negation or modal wording changed", reasons)

    def test_number_and_percent_edits_keep_offsets(self):
        a, b = "Gross margin was 24.0%.", "Gross margin was 21.0%."
        edits = edit_spans(a, b)
        self.assertTrue(any("24" in x["old"]["text"] for x in edits))
        for edit in edits:
            for side, text in (("old", a), ("new", b)):
                span = edit[side]
                self.assertEqual(text[span["start"]:span["end"]], span["text"])

    def test_unrelated_passages_remain_unmatched(self):
        changes = compare(simple_pair(["Earthquake destroyed the assembly facility."], ["We issued preferred securities to investors."]))["changes"]
        self.assertEqual(sorted(c["kind"] for c in changes), ["added", "removed"])
        self.assertTrue(all(c["ambiguous_alignment"] for c in changes))

    def test_threshold_rejects_nan_and_invalid_values(self):
        for threshold in (-1, 0, 2, float("nan")):
            with self.assertRaises(TrackerError):
                compare(simple_pair(["a"], ["b"]), threshold=threshold)

    def test_review_fixes_alignment_and_rank_without_source_edit(self):
        pair = simple_pair(["Competitive pressure is a concern."], ["Rivals bundle maintenance with equipment."])
        review = {"pair_fingerprint": "test-pair", "alignments": [{"old": "risk-0001", "new": "risk-0001"}]}
        corrected = compare(pair, review)["changes"]
        self.assertEqual(len(corrected), 1)
        self.assertEqual(corrected[0]["method"], "reviewer")
        review["reviews"] = {corrected[0]["id"]: {"priority": "low", "status": "accepted", "note": "Reviewed against both sources."}}
        result = compare(pair, review)["changes"][0]
        self.assertEqual((result["priority"], result["status"], result["needs_review"]), ("low", "accepted", False))

    def test_review_can_split_a_match(self):
        pair = simple_pair(["Customer A left the market."], ["Customer B left the market."])
        review = {"pair_fingerprint": "test-pair", "alignments": [{"old": "risk-0001", "new": None}, {"old": None, "new": "risk-0001"}]}
        self.assertEqual(sorted(c["kind"] for c in compare(pair, review)["changes"]), ["added", "removed"])

    def test_stale_conflicting_and_unknown_reviews_fail(self):
        pair = simple_pair(["a"], ["a"])
        bad = [
            {"pair_fingerprint": "stale"},
            {"pair_fingerprint": "test-pair", "alignments": [{"old": "risk-0001", "new": "risk-0001"}] * 2},
            {"pair_fingerprint": "test-pair", "reviews": {"unknown": {"priority": "high"}}},
            {"pair_fingerprint": "test-pair", "alignments": [{"old": "missing", "new": None}]},
        ]
        for review in bad:
            with self.assertRaises(TrackerError):
                compare(pair, review)

    def test_malformed_review_fields_do_not_silently_apply(self):
        pair = simple_pair(["a"], ["b"])
        for review in [{"pair_fingerprint": "test-pair", "review": {}},
                       {"pair_fingerprint": "test-pair", "alignments": {}},
                       {"pair_fingerprint": "test-pair", "alignments": ["bad"]}]:
            with self.assertRaises(TrackerError):
                compare(pair, review)

    def test_bundled_review_joins_two_missed_pairs_and_promotes_buyback(self):
        pair = fixture("challenge")
        review = json.loads((FIXTURES / "challenge-review.json").read_text())
        baseline = compare(pair)
        corrected = compare(pair, review)
        self.assertEqual(len(baseline["changes"]) - len(corrected["changes"]), 2)
        buyback = next(c for c in corrected["changes"] if c["old"] and c["old"]["dom_id"] == "buyback")
        self.assertEqual((buyback["priority"], buyback["status"]), ("high", "accepted"))
        for original in ["competition", "litigation"]:
            change = next(c for c in corrected["changes"] if c["old"] and c["old"]["dom_id"] == original)
            self.assertEqual((change["kind"], change["method"]), ("changed", "reviewer"))


class ManifestTests(unittest.TestCase):
    def mutate(self, field, value, index=1):
        data = json.loads((FIXTURES / "development-pair.json").read_text())
        for doc in data["documents"]:
            doc["path"] = str(FIXTURES / doc["path"])
        data["documents"][index][field] = value
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pair.json"
            path.write_text(json.dumps(data))
            return load_pair(path)

    def test_hash_mismatch_rejected(self):
        with self.assertRaisesRegex(TrackerError, "SHA-256 mismatch"):
            self.mutate("sha256", "0" * 64)

    def test_company_period_form_and_id_guards(self):
        for key, value in [("cik", "other"), ("fiscal_year", 2026), ("form", "10-K/A"), ("id", "../../escape"), ("filed", "2000-01-01")]:
            with self.assertRaises((TrackerError, ValueError)):
                self.mutate(key, value)


class ReportAndEvaluationTests(unittest.TestCase):
    def test_export_all_evidence_links_offsets_and_review_preservation(self):
        pair = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report"
            result = compare(pair)
            write_report(pair, result, out)
            self.assertIn("SYNTHETIC FIXTURE", (out / "memo.md").read_text())
            for change in result["changes"]:
                for side in ("old", "new"):
                    if change[side]:
                        target, anchor = change[side + "_citation"].split("#")
                        self.assertIn('id="%s"' % anchor, (out / target).read_text())
                        meta = result[side]
                        self.assertEqual(digest((out / "sources" / (meta["id"] + ".original.html")).read_bytes()), meta["sha256"])
            with (out / "changes.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(result["changes"]))
            (out / "review.json").write_text('{"keep":"my edits"}')
            write_report(pair, result, out)
            self.assertEqual((out / "review.json").read_text(), '{"keep":"my edits"}')

    def test_export_does_not_overwrite_source_folder(self):
        pair = fixture()
        with self.assertRaisesRegex(TrackerError, "source documents"):
            write_report(pair, compare(pair), FIXTURES)

    def test_new_report_invalidates_old_metrics(self):
        pair = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report"
            out.mkdir()
            (out / "metrics.json").write_text('{"stale":true}')
            write_report(pair, compare(pair), out)
            self.assertFalse((out / "metrics.json").exists())

    def test_spreadsheet_formula_escaping(self):
        self.assertEqual(safe_csv("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(safe_csv("  +1"), "'  +1")
        self.assertEqual(safe_csv("Revenue $10"), "Revenue $10")

    def test_evaluation_raw_counts_and_known_challenge_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics = evaluate(FIXTURES / "challenge-pair.json", FIXTURES / "challenge-gold.json", Path(tmp) / "report")
        self.assertGreaterEqual(metrics["gold_changes"], 10)
        self.assertEqual(metrics["true_positive"] + metrics["false_negative"], metrics["gold_changes"])
        self.assertEqual(metrics["true_positive"] + metrics["false_positive"], metrics["predicted_changes"])
        self.assertIn(["competition", "competition_rewrite", "changed"], metrics["missed_gold_decisions"])
        self.assertEqual(metrics["local_citation_integrity"]["value"], 1.0)

    def test_cli_runs_from_separate_process_without_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run([sys.executable, "-m", "filing_tracker", "compare", "fixtures/development-pair.json", "--out", str(Path(tmp) / "report")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["provenance"], "synthetic")

    def test_cli_invalid_manifest_returns_two(self):
        with redirect_stderr(io.StringIO()) as err:
            status = main(["compare", "/no/such/manifest.json", "--out", "/not-written"])
        self.assertEqual(status, 2)
        self.assertIn("Cannot load pair", err.getvalue())


class SECTests(unittest.TestCase):
    def test_contact_required(self):
        with self.assertRaisesRegex(TrackerError, "contact email"):
            SECClient("anonymous")

    def test_fetch_checks_history_and_preserves_source_hashes_with_mock(self):
        annuals = {"accessionNumber": ["0000000001-24-000001", "0000000001-23-000001"], "form": ["10-K", "10-K"], "filingDate": ["2025-02-15", "2024-02-15"], "reportDate": ["2024-12-31", "2023-12-31"], "primaryDocument": ["annual.htm", "annual.htm"]}
        class Client:
            def get(self, url):
                if "submissions/" in url:
                    return json.dumps({"name": "MOCK ONLY", "cik": "1", "filings": {"recent": annuals, "files": []}}).encode()
                return (FIXTURES / "alder-2024.html").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            path = fetch_pair("1", annuals["accessionNumber"], Path(tmp) / "download", "tester@example.invalid", Client())
            pair = load_pair(path)
            self.assertEqual(pair["old"]["metadata"]["fiscal_year"], 2023)
            self.assertEqual(pair["new"]["metadata"]["fiscal_year"], 2024)
            self.assertTrue(pair["old"]["metadata"]["source_url"].startswith("https://www.sec.gov/Archives/"))
            with self.assertRaisesRegex(TrackerError, "new or empty"):
                fetch_pair("1", annuals["accessionNumber"], path.parent, "tester@example.invalid", Client())

    def test_fetch_rejects_nonannual_or_absent_accessions(self):
        class Client:
            def get(self, url):
                return json.dumps({"name": "MOCK ONLY", "filings": {"recent": {"accessionNumber": [], "form": [], "filingDate": [], "reportDate": [], "primaryDocument": []}}}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(TrackerError, "original 10-Ks"):
                fetch_pair("1", ["0000000001-24-000001", "0000000001-23-000001"], Path(tmp) / "download", "tester@example.invalid", Client())


if __name__ == "__main__":
    unittest.main()
