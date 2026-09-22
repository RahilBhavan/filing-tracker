"""Sample-scoped evaluation; unlabelled predictions never count as irrelevant."""
import hashlib
import json
import time
from pathlib import Path
from .core import TrackerError, compare, load_pair
from .alignment import members
from .evaluation import fraction


def change_key(c):
    return (tuple(b['id'] for b in members(c['old'])), tuple(b['id'] for b in members(c['new'])), c['kind'])


def score(pair, gold, engine='v2', assumptions=None):
    if gold['pair_fingerprint'] != pair['fingerprint']:
        raise TrackerError('Labels belong to a different pair')
    expected = {(tuple(x['old']), tuple(x['new']), x['kind']): x for x in gold['labels']}
    covered = {side: {b for x in gold['labels'] for b in x[side]} for side in ('old','new')}
    for side in covered:
        if not covered[side] <= {b['id'] for b in pair[side]['blocks']}:
            raise TrackerError('Label references an absent source block')
    if len(expected) != len(gold['labels']):
        raise TrackerError('Duplicate labels')
    started = time.perf_counter()
    result = compare(pair, engine=engine, assumptions=assumptions)
    seconds = time.perf_counter() - started
    actual = {change_key(c) for c in result['changes']}
    changed = {k for k in expected if k[2] != 'unchanged'}
    important = {k for k,v in expected.items() if v['importance']==2 and k[2]!='unchanged'}
    ranked = [change_key(c) for c in result['changes'] if c['kind']!='unchanged']
    top = ranked[:10]
    judged = [k for k in top if k in expected]
    noise = sum(expected[k]['importance']==0 for k in judged)
    touched = {k for k in actual if set(k[0]) & covered['old'] or set(k[1]) & covered['new']}
    return {'engine':engine,'comparison_seconds':round(seconds,4),'label_count':len(expected),
        'scope':gold['scope'],'independent_review':gold['independent_review'],
        'changed_decision_recall':fraction(len(changed & actual),len(changed)),
        'important_change_recall':fraction(len(important & actual),len(important)),
        'important_change_recall_at_10':fraction(len(important & set(top)),len(important)),
        'exact_alignment_and_type':fraction(len(set(expected) & actual),len(expected)),
        'labelled_decisions_needing_correction':len(set(expected)-actual),
        'predictions_touching_labelled_blocks':len(touched),
        'top_10':{'count':len(top),'judged':len(judged),'unjudged':len(top)-len(judged),
                  'known_irrelevant':noise,'known_relevant':sum(expected[k]['importance']>=1 for k in judged),
                  'noise_rate_among_judged':fraction(noise,len(judged))},
        'missed_labels':[v['id'] for k,v in expected.items() if k not in actual],
        'measurement_note':'Correction count is unmatched author decisions, not measured user actions. Unjudged top-ten items remain unknown.'}


def freeze(root):
    paths = sorted((root/'filing_tracker').glob('*.py'))
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def run(root):
    root=Path(root)
    results=[]
    for name in ('msft-2022-2023','msft-2023-2024','brk-2023-2024'):
        pair=load_pair(root/'corpus'/f'{name}.json')
        gold=json.loads((root/'corpus/labels'/f'{name}.json').read_text())
        for engine in ('v1','v2'):
            results.append(dict(pair=name,**score(pair,gold,engine)))
    output={'engine_hashes':freeze(root),'results':results,'human_timing':{'completed_sessions':0,'time_savings':None,'status':'Pending independent human sessions'}}
    (root/'docs/real-benchmark.json').write_text(json.dumps(output,indent=2)+'\n')
    return output
