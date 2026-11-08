"""Generate the full workbook in programme-year parts offline and validate each combined result."""
import json, sys, time, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'backend'))
from app.provenance import CONFIG
from app.solver import generate
from app.validation import validate_schedule
from app.partial_plan import scope_activities, progress
limit = int(sys.argv[1]); cap = int(sys.argv[2]) if len(sys.argv) > 2 else 600
snap = json.load(open('fullsnap.json'))
from app.positions import tas_without_teaching
idle = set(tas_without_teaching([r for r in snap['records'] if r['kind'] == 'instructors'], [r for r in snap['records'] if r['kind'] == 'courses']))
print('TAs with no activity of their own in the workbook:', len(idle), 'of', sum(r.get('position') == 'ta' for r in snap['records']), flush=True)
# Experiment only: leave those TAs out, so the hard "every TA teaches" rule can hold.
snap['records'] = [dict(r, eligible_instructors=[t for t in r['eligible_instructors'] if t not in idle]) if r['kind'] == 'courses' else r for r in snap['records'] if r['id'] not in idle]
# Experiment only: placeholder TA pools at most half loaded, and no activity without a big-enough room.
import math, itertools
from app.preflight import inspect_inputs
noroom = {b['activity_id'] for b in inspect_inputs(snap)['blockers'] if b['code'] == 'no_suitable_room'}
snap['records'] = [r for r in snap['records'] if r['id'] not in noroom]
by = {r['id']: r for r in snap['records']}
days = snap['calendar']['days']; day_minutes = sum(p['end'] - p['start'] for p in snap['calendar']['teaching_periods'])
pools = collections.defaultdict(list)
for r in snap['records']:
    if r['kind'] == 'courses' and r['activity_type'] != 'lecture': pools[tuple(sorted(r['eligible_instructors']))].append(r)
extra, n = [], itertools.count()
for pool, items in pools.items():
    need = sum(a['duration'] * a['sessions'] for a in items)
    have = len(pool) * day_minutes * (len(days) - 1)
    add = max(0, min(math.ceil(2 * need / (day_minutes * (len(days) - 1))) - len(pool), len(items) - len(pool)))
    new = [{'id': f'extra-ta-{next(n)}', 'kind': 'instructors', 'name': 'Extra placeholder TA', 'position': 'ta', 'day_off': days[i % len(days)]} for i in range(add)]
    extra += new
    for a in items: a['eligible_instructors'] = a['eligible_instructors'] + [t['id'] for t in new]
snap['records'] += extra
print('set aside', len(noroom), 'activities without a big-enough room; added', len(extra), 'placeholder TAs', flush=True)
if 'morerooms' in sys.argv:
    # Experiment: copy rooms until each kind is at most ~60% loaded.
    week = len(days) * day_minutes
    for kind in ('lab', 'lecture'):
        need = sum(a['duration'] * a['sessions'] for a in snap['records'] if a['kind'] == 'courses' and (a['activity_type'] == 'lab') == (kind == 'lab'))
        mine = [r for r in snap['records'] if r['kind'] == 'rooms' and kind in (r.get('room_types') or [r.get('room_type')])]
        extra_rooms = max(0, math.ceil(need / (0.6 * week)) - len(mine))
        snap['records'] += [{**mine[i % len(mine)], 'id': f'extra-room-{kind}-{i}', 'code': f'X-{kind}-{i}', 'name': 'Placeholder room'} for i in range(extra_rooms)]
        print('added', extra_rooms, kind, 'rooms', flush=True)
if 'nopolicy' in sys.argv:
    snap['calendar'] = {**snap['calendar'], 'realism_policy': {}}  # experiment: daily policies off
snap['provenance'] = {'solver_config': {**CONFIG, 'time_limit_seconds': limit}}
groups = {r['id']: r for r in snap['records'] if r['kind'] == 'groups'}
size = collections.Counter()
for a in (r for r in snap['records'] if r['kind'] == 'courses'):
    for k in {(groups[g]['major'], groups[g]['year']) for g in a['group_ids']}: size[k] += a['sessions']
batches, current, n = [], [], 0
for key, count in size.most_common():
    if n + count > cap: batches.append(current); current, n = [], 0
    current.append(key); n += count
batches.append(current)
print(len(batches), 'parts:', [sum(size[k] for k in b) for b in batches], flush=True)
fixed = []
for i, batch in enumerate(batches, 1):
    scope = [{'programme': p, 'year': y} for p, y in batch]
    part = {**snap, 'plan': {'scope': scope, 'base_run_id': None, 'activity_ids': scope_activities(snap['records'], scope, {r['activity_id'] for r in fixed}), 'fixed': fixed}}
    t = time.time(); res = generate(part)
    if res['status'] != 'completed':
        print(i, res['status'], res.get('reason'), res.get('activity_id'), round(time.time() - t), 's'); break
    report = validate_schedule(part, res['assignments'])
    kept = all(r in res['assignments'] for r in fixed)
    print(i, 'completed', round(time.time() - t), 's valid', report['passed'], report['errors'], 'fixed kept', kept, progress(part)['scheduled_sessions'], res.get('objective_components'), flush=True)
    if not report['passed']: break
    fixed = res['assignments']
json.dump(fixed, open('full_parts_result.json', 'w'))
if fixed and progress(part)['complete']:
    whole = validate_schedule(snap, fixed)
    print('whole timetable valid without plan:', whole['passed'], whole['errors'])
