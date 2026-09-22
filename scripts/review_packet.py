"""Create source-only reviewer tasks without model matches, priorities, or labels."""
import csv
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from filing_tracker.core import load_pair

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'corpus/blind-review'
OUT.mkdir(exist_ok=True)
for name in ['msft-2022-2023','msft-2023-2024','brk-2023-2024']:
    pair=load_pair(ROOT/'corpus'/f'{name}.json')
    # All extracted passages, not only the author's selected sample.
    packet={'pair':name,'pair_fingerprint':pair['fingerprint'],'reviewer':'','independent_review':True,
        'instructions':'Read both sources. Match each earlier passage to zero, one, or consecutive later passages; add rows for new passages. Fill kind and importance (0 routine, 1 useful, 2 investment-relevant). Cite original block IDs and explain judgment. Do not inspect labels or model reports before submitting.',
        'sources':{side:{'metadata':pair[side]['metadata'],'blocks':pair[side]['blocks']} for side in ['old','new']}}
    (OUT/f'{name}-sources.json').write_text(json.dumps(packet,indent=2,ensure_ascii=False)+'\n')
    with (OUT/f'{name}-decisions.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['old_ids','new_ids','kind','importance','rationale','reviewer'])
        for b in pair['old']['blocks']:writer.writerow([b['id'],'','','','',''])
(OUT/'README.md').write_text('''# Independent review packet

These packets contain source passages and blank decisions, without model alignments or author priorities. Match all earlier passages and add rows for new passages. Use semicolons for consecutive grouped IDs. Kinds: unchanged, changed, added, removed. Importance: 0 routine, 1 useful, 2 investment-relevant. Fill a reviewer name and rationale.

Open the original files in ../originals/ and inspect each packet's source locator (DOCX paragraph or PDF page/bounding box). Do not read ../labels/ or ../../demo/ before submitting. Resolve disagreements with a second reviewer; retain both original submissions. Author labels are development examples, not independent validation.

## Human timing protocol

Use at least two reviewers and different pairs, counterbalancing manual and assisted order. Give each reviewer the same goal: identify the ten most investment-relevant changes, cite them, and write a short rationale. Start the in-app timer only when reading begins; finish after saving the last decision. Record interruptions because wall time includes idle time. The manual view omits predictions; the assisted view shows the ranked queue. Avoid using the same pair twice with one reviewer. Independently grade accuracy before interpreting faster completion as an improvement. Report participant count, pair, order, elapsed time, important-change recall, and corrections. Automated browser-test sessions are not human timing evidence.

No human sessions have been collected for this release.
''')
print('Created source-only packets and blank decisions in',OUT)
