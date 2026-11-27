"""Compare a JadwAI-generated timetable with the real GIU timetable built from the same staff planning.

The real timetable is a human grid without stable course codes, so sessions are compared at the level of
faculty, cohort (semester + faculty), student group number, day and period, not one session against one
session. Language classes in the real grid (not in the staff planning) are left out. Output: a Markdown
report with aggregate figures only (no staff names).

    JADWAI_URL=http://127.0.0.1:8012 JADWAI_EMAIL=... JADWAI_PASSWORD=... \\
      python scripts/compare_giu_timetable.py REAL.xlsx [--run RUN_ID] [--out report.md]
"""
import argparse
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_giu_timetable import read  # noqa: E402

DAYS = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
STARTS = [510, 615, 720, 825, 945]
FACULTIES = ['BA', 'BI', 'ENG', 'INF', 'PHARMA', 'BIO', 'ARCH', 'DESIGN', 'PT']


def faculty_of_major(major):
    m = (major or '').lower()
    if m.startswith('ba'): return 'BA'
    if m == 'bi': return 'BI'
    if m.startswith('bio'): return 'BIO'
    if m.startswith('pharma'): return 'PHARMA'
    if m.startswith(('inf', 'cs ')): return 'INF'
    if m.startswith('arch') or 'interior' in m: return 'ARCH'
    if 'design' in m: return 'DESIGN'
    if 'physical' in m: return 'PT'
    return 'ENG'


def idle(periods):
    """Empty periods between a group's first and last session of a day."""
    return sum(1 for p in range(min(periods), max(periods)) if p not in periods) if periods else 0


def jadwai(base, run_id):
    c = httpx.Client(base_url=base.rstrip('/') + '/api', headers={'X-Jadwai-Request': '1'}, timeout=300)
    c.post('/auth/login', json={'email': os.environ['JADWAI_EMAIL'], 'password': os.environ['JADWAI_PASSWORD']}).raise_for_status()
    if not run_id:
        runs = c.get('/schedules?summary=true').json()
        run_id = next(r['id'] for r in runs if r['status'] == 'completed' and re.search(r'part (\d+)/\1$', r.get('name') or '') or (r['status'] == 'completed' and not r.get('name')))
    run = c.get(f'/schedules/{run_id}').json()
    recs = {r['id']: r for r in run['snapshot']['records']}
    out = []
    for a in run['result']['assignments']:
        act = recs[a['activity_id']]
        groups = [recs[g] for g in act['group_ids']]
        room = recs[a['room_id']]
        for p in range((a['end_minute'] - a['start_minute'] + 15) // 105 or 1):
            out.append({'day': a['day'], 'period': STARTS.index(a['start_minute']) + p, 'kind': act['activity_type'], 'course': act['name'],
                        'groups': [(faculty_of_major(g.get('major')), (g.get('year') or 0) * 2, g['code']) for g in groups],
                        'room': room['code'], 'placeholder_room': room['code'].startswith('X')})
    return run_id, out


def real_groups(sessions):
    """Per real student group (faculty, semester, stream, number): the (day, period) cells it attends.
    Numbered cells belong to their group; cells without a number (mostly lectures) to every group of the stream."""
    teach = [s for s in sessions if s['kind'] == 'teaching' and s['faculty']]
    streams = defaultdict(set)
    for s in teach:
        for g in s['groups']:
            streams[(s['faculty'], s['semester'], s['stream'])].add(g)
    attend = defaultdict(set)
    for s in teach:
        key = (s['faculty'], s['semester'], s['stream'])
        for g in (s['groups'] or streams[key]):
            attend[(*key, g)].add((s['day'], s['period']))
    return attend


def summary(attend_by_group):
    days = [len({d for d, _ in cells}) for cells in attend_by_group.values()]
    gaps = []
    for cells in attend_by_group.values():
        per_day = defaultdict(set)
        for d, p in cells:
            per_day[d].add(p)
        gaps.append(sum(idle(ps) for ps in per_day.values()))
    n = len(days)
    return {'groups': n, 'days_mean': statistics.mean(days) if n else 0, 'six_days': sum(1 for d in days if d == 6), 'max3': sum(1 for d in days if d <= 3),
            'gaps_mean': statistics.mean(gaps) if n else 0, 'no_gaps': sum(1 for g in gaps if g == 0)}


def pct(counter, keys):
    total = sum(counter.values()) or 1
    return [f'{100 * counter.get(k, 0) / total:.0f}%' for k in keys]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('real'); ap.add_argument('--run'); ap.add_argument('--out')
    args = ap.parse_args()
    real, rooms = read(args.real)
    run_id, gen = jadwai(os.environ.get('JADWAI_URL', 'http://127.0.0.1:8012'), args.run)
    teach = [s for s in real if s['kind'] == 'teaching' and s['faculty']]
    lines = [f'# JadwAI and the real Spring 2024 timetable', '',
             f'JadwAI run `{run_id}`. Real timetable: {len(teach)} teaching cells (a cell is one period of one session; '
             f'{sum(1 for s in real if s["kind"] == "language")} language-class cells and the 6 day sheets\' "Day off" cells left out). '
             f'JadwAI: {len(gen)} session-periods.', '']
    # Where in the week
    rd, gd = Counter(s['day'] for s in teach), Counter(s['day'] for s in gen)
    rp, gp = Counter(s['period'] for s in teach), Counter(s['period'] for s in gen)
    lines += ['## Spread over the week', '', '| | ' + ' | '.join(d[:3] for d in DAYS) + ' |', '|---|' + '---|' * len(DAYS),
              '| Real | ' + ' | '.join(pct(rd, DAYS)) + ' |', '| JadwAI | ' + ' | '.join(pct(gd, DAYS)) + ' |', '',
              '| | 08:30 | 10:15 | 12:00 | 13:45 | 15:45 |', '|---|---|---|---|---|---|',
              '| Real | ' + ' | '.join(pct(rp, range(5))) + ' |', '| JadwAI | ' + ' | '.join(pct(gp, range(5))) + ' |', '']
    # Per faculty volume
    rf = Counter(s['faculty'] for s in teach)
    gf = Counter(g[0] for s in gen for g in s['groups'][:1])
    lines += ['## Teaching per faculty (session-periods)', '', '| Faculty | Real | JadwAI |', '|---|---|---|']
    lines += [f'| {f} | {rf.get(f, 0)} | {gf.get(f, 0)} |' for f in FACULTIES] + ['']
    # Cohort days
    rc, gc = defaultdict(set), defaultdict(set)
    for s in teach:
        rc[(s['faculty'], s['semester'])].add(s['day'])
    for s in gen:
        for f, sem, _ in s['groups']:
            gc[(f, sem)].add(s['day'])
    both = sorted(set(rc) & set(gc), key=lambda k: (FACULTIES.index(k[0]) if k[0] in FACULTIES else 99, k[1] or 0))
    lines += ['## Days with teaching per cohort', '', '| Cohort | Real | JadwAI |', '|---|---|---|']
    lines += [f'| {f} sem {sem} | {len(rc[(f, sem)])} | {len(gc[(f, sem)])} |' for f, sem in both]
    lines += ['', f'Mean over these {len(both)} cohorts: real {statistics.mean(len(rc[k]) for k in both):.1f} days, JadwAI {statistics.mean(len(gc[k]) for k in both):.1f} days.', '']
    # Per student group
    rg = real_groups(real)
    gg = defaultdict(set)
    for s in gen:
        for g in s['groups']:
            gg[g].add((s['day'], s['period']))
    R, G = summary(rg), summary(gg)
    lines += ['## Per student group', '', '| | Real | JadwAI |', '|---|---|---|',
              f"| Groups | {R['groups']} | {G['groups']} |",
              f"| Days on campus (mean) | {R['days_mean']:.1f} | {G['days_mean']:.1f} |",
              f"| Groups on campus all 6 days | {R['six_days']} ({100 * R['six_days'] / max(R['groups'], 1):.0f}%) | {G['six_days']} ({100 * G['six_days'] / max(G['groups'], 1):.0f}%) |",
              f"| Groups on campus at most 3 days | {R['max3']} ({100 * R['max3'] / max(R['groups'], 1):.0f}%) | {G['max3']} ({100 * G['max3'] / max(G['groups'], 1):.0f}%) |",
              f"| Empty periods between classes per week (mean) | {R['gaps_mean']:.1f} | {G['gaps_mean']:.1f} |",
              f"| Groups with no empty periods | {R['no_gaps']} ({100 * R['no_gaps'] / max(R['groups'], 1):.0f}%) | {G['no_gaps']} ({100 * G['no_gaps'] / max(G['groups'], 1):.0f}%) |", '']
    # Rooms
    real_rooms = defaultdict(int)
    for r in rooms:
        for p, v in enumerate(r['counts']):
            try:
                real_rooms[(r['day'], p)] += int(float(str(v).strip()))
            except (TypeError, ValueError):
                pass
    gen_rooms = defaultdict(set)
    for s in gen:
        gen_rooms[(s['day'], s['period'])].add(s['room'])
    rr = [real_rooms.get((d, p), 0) for d in DAYS for p in range(5)]
    gr = [len(gen_rooms.get((d, p), ())) for d in DAYS for p in range(5)]
    lines += ['## Rooms in use per period', '', '| | Mean | Peak |', '|---|---|---|',
              f'| Real (the grid\'s own room counts) | {statistics.mean(rr):.0f} | {max(rr)} |',
              f'| JadwAI (distinct rooms) | {statistics.mean(gr):.0f} | {max(gr)} |', '',
              f"JadwAI used placeholder rooms for {sum(1 for s in gen if s['placeholder_room'])} of {len(gen)} session-periods.", '']
    text = '\n'.join(lines)
    if args.out:
        Path(args.out).write_text(text)
    print(text)


if __name__ == '__main__':
    main()
