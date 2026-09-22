"""Reproduce the real, author-labelled sample comparison."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from filing_tracker.benchmark import run
if __name__=='__main__':
    result=run(Path(__file__).resolve().parents[1])
    for row in result['results']:
        print(row['pair'],row['engine'],'recall',row['changed_decision_recall'],'corrections',row['labelled_decisions_needing_correction'])
