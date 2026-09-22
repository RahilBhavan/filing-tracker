"""Report recorded sessions; never infer time savings from an unmatched pair."""
import json
import sys
from pathlib import Path
sessions=[]
for filename in sys.argv[1:]:
    state=json.loads(Path(filename).read_text())
    sessions.extend(dict(pair_fingerprint=state['pair_fingerprint'],**s) for s in state['sessions'] if s.get('ended'))
print(json.dumps({'completed_sessions':len(sessions),'sessions':sessions,'time_savings':None,'note':'Compare counterbalanced, accuracy-graded human sessions separately. Wall time includes idle time.'},indent=2))
