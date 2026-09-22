"""Run with python3 -m filing_tracker from the project folder."""

import argparse
import json
import sys
from pathlib import Path

from .core import TrackerError, compare, load_pair
from .evaluation import evaluate
from .report import write_report
from .sec import fetch_pair


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cited annual-filing comparison; standard library only")
    sub = parser.add_subparsers(dest="command", required=True)
    compare_parser = sub.add_parser("compare", help="Compare an explicit local source manifest")
    compare_parser.add_argument("manifest")
    compare_parser.add_argument("--out", required=True)
    compare_parser.add_argument("--review", help="JSON alignment overrides and review decisions")
    compare_parser.add_argument("--threshold", type=float, default=0.62)
    eval_parser = sub.add_parser("evaluate", help="Evaluate a pair against author-labeled gold decisions")
    eval_parser.add_argument("manifest")
    eval_parser.add_argument("--gold", required=True)
    eval_parser.add_argument("--out", required=True)
    fetch_parser = sub.add_parser("fetch", help="Fetch a consecutive annual pair from SEC EDGAR")
    fetch_parser.add_argument("--cik", required=True)
    fetch_parser.add_argument("--accessions", nargs=2, required=True)
    fetch_parser.add_argument("--out", required=True)
    fetch_parser.add_argument("--user-agent", required=True)
    compare_parser.add_argument("--engine", choices=["v1", "v2"], default="v2")
    compare_parser.add_argument("--assumptions")
    serve_parser = sub.add_parser("serve", help="Open a persistent local browser review")
    serve_parser.add_argument("manifest")
    serve_parser.add_argument("--out", required=True)
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--assumptions")
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            pair = load_pair(args.manifest)
            review = json.loads(Path(args.review).read_text(encoding="utf-8")) if args.review else None
            result = compare(pair, review, args.threshold, assumptions=json.loads(Path(args.assumptions).read_text()) if args.assumptions else None, engine=args.engine)
            out = write_report(pair, result, args.out)
            print(json.dumps({"out": str(out), "provenance": result["provenance"], "changes": len(result["changes"])}))
        elif args.command == "evaluate":
            metrics = evaluate(args.manifest, args.gold, args.out)
            print(json.dumps(metrics, indent=2))
        elif args.command == "serve":
            from .review_app import serve
            serve(args.manifest, args.out, args.port, json.loads(Path(args.assumptions).read_text()) if args.assumptions else None)
        else:
            print(fetch_pair(args.cik, args.accessions, args.out, args.user_agent))
        return 0
    except (TrackerError, OSError, ValueError, KeyError, TypeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
