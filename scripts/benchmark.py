"""Reproduce the real, author-labelled sample comparison.

Writes build/real-benchmark.json by default; pass --update to rewrite the tracked
docs/real-benchmark.json (its timings change on every run).
"""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from filing_tracker.benchmark import run
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update',action='store_true',help='rewrite docs/real-benchmark.json')
    args=parser.parse_args()
    result=run(ROOT,ROOT/'docs/real-benchmark.json' if args.update else None)
    for row in result['results']:
        print(row['pair'],row['engine'],'recall',row['changed_decision_recall'],'corrections',row['labelled_decisions_needing_correction'])
