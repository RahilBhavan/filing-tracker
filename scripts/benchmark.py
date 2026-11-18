"""Reproduce the real, author-labelled sample comparison.

Writes build/real-benchmark.json by default; pass --update to rewrite the tracked
docs/real-benchmark.json (its timings change on every run). --check exits 1 when
the tracked record no longer matches a fresh run, ignoring timings.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from filing_tracker.benchmark import drift, run
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update',action='store_true',help='rewrite docs/real-benchmark.json')
    parser.add_argument('--check',action='store_true',help='fail if docs/real-benchmark.json is stale')
    args=parser.parse_args()
    if args.update and args.check:
        parser.error('--update and --check are exclusive')
    recorded=ROOT/'docs/real-benchmark.json'
    result=run(ROOT,recorded if args.update else None)
    for row in result['results']:
        print(row['pair'],row['engine'],'recall',row['changed_decision_recall'],'corrections',row['labelled_decisions_needing_correction'])
    if args.check:
        stale=drift(result,json.loads(recorded.read_text()))
        for path in stale:
            print('stale:',path,file=sys.stderr)
        if stale:
            sys.exit('docs/real-benchmark.json differs from this run; rerun with --update')
