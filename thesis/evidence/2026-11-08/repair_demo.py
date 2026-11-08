"""Offline: the demo timetable made impossible in two ways, then diagnosed."""
import json, sys, time, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'backend'))
from app.repair import diagnose, candidates
from app.solver import generate
run = json.load(open('report_run.json')); base = run['snapshot']
recs = {r['id']: r for r in base['records']}
# A lecture whose only instructor we make unavailable all week, plus two locked sessions of G7 at the same time.
lecture = next(r for r in base['records'] if r['kind'] == 'courses' and r['activity_type'] == 'lecture' and len(r['eligible_instructors']) == 1)
teacher = lecture['eligible_instructors'][0]
g7 = next(r for r in base['records'] if r['kind'] == 'groups' and r['name'].endswith('Core G7') and r.get('year') == 3)
g7_acts = [r['id'] for r in base['records'] if r['kind'] == 'courses' and g7['id'] in r['group_ids']][:2]
snap = copy.deepcopy(base)
snap['rules'] = [{'id': 'away', 'status': 'approved', 'type': 'unavailable', 'title': f"{recs[teacher]['name']} away all week", 'instructor_id': teacher, 'day': None, 'start_hour': 8, 'end_hour': 18}]
snap['assignment_locks'] = [{'id': f'lock{i}', 'status': 'approved', 'activity_id': a, 'occurrence': 0, 'day': 'Sunday', 'start_minute': 615} for i, a in enumerate(g7_acts)]
print('candidates', len(candidates(snap)))
t = time.time(); print('strict:', generate({**snap, 'provenance': {'solver_config': {**__import__('app.provenance', fromlist=['CONFIG']).CONFIG, 'objective_profile': 'preferences-first-v1', 'time_limit_seconds': 30}}})['status'], round(time.time() - t), 's', flush=True)
t = time.time(); r = diagnose(snap, budget=240, step=30, hints=[lecture['id']])
print(r['status'], 'verified', r.get('verified'), r.get('solves'), 'solves', round(time.time() - t), 's', r.get('message', ''))
for f in r.get('suggestions', []):
    print('-', f['title'], '|', f['message']); [print('    ', x) for x in f['sessions'][:3]]
