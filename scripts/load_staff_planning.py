"""Load a GIU staff-planning workbook (one sheet per faculty) into an EMPTY JadwAI workspace.

Each sheet row is one course: code, name, "Offered to" (semester and programme), weekly hours per group
(L lecture, E exercise/tutorial, P practical/lab), intake, number of lecture groups and tutorial/lab
groups, lecturer and the number of TAs needed. Rows without a course code under a course are extra
lecturers of that course. Rooms and the teaching week come from a JSON file (see --rooms).

Interpretation (agreed with the workbook's owner, 27 November 2026):
  * an hour is 60 minutes and a session is 90 minutes: weekly minutes = hours x 60, scheduled as the
    nearest whole number of 90-minute sessions (at least one); planned minutes are kept per activity;
  * TAs are not named: "<course> TA k" placeholders, as many as the TA count rounded up;
  * "N.N." or a missing lecturer becomes one placeholder lecturer per course;
  * "Supervised by Dr X" with no lecture hours adds no lecturer (the TAs teach);
  * each cohort ("2nd INF") gets as many student groups as its largest tutorial-group count; a course
    offered to several cohorts ("2nd BA & BI") shares their groups; lecture groups split them evenly.

    JADWAI_URL=http://127.0.0.1:8012 JADWAI_EMAIL=... JADWAI_PASSWORD=... \\
      python scripts/load_staff_planning.py WORKBOOK.xlsx --rooms rooms.json [--commit] [--clear]
Without --commit it only reads the workbook and prints the plan.
"""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

from openpyxl import load_workbook

PROGRAMMES = {'BA', 'BI', 'ENG', 'INF', 'PHARMA', 'BIO', 'DESIGN', 'ARCH'}


def norm(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def column(header, *names, exact=False, last=False):
    hits = [i for i, h in enumerate(header) if h and any((norm(h).lower() == n.lower()) if exact else (n.lower() in norm(h).lower()) for n in names)]
    return (hits[-1] if last else hits[0]) if hits else None


def number(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def sessions_for(hours):
    """Nearest whole number of 90-minute sessions for `hours` 60-minute hours (at least one)."""
    return max(1, int(hours * 60 / 90 + 0.5)) if hours > 0 else 0


def cohorts_of(offered):
    """'2nd BA & BI' -> [('2', 'BA'), ('2', 'BI')]; '6th ENG ( All Majors)' -> [('6', 'ENG')]."""
    out = []
    for line in re.split(r'\n|/(?=\s*\d)', str(offered or '')):
        line = norm(line)
        m = re.match(r'(\d+)(?:st|nd|rd|th)\b\s*-?\s*(.*)', line, re.I)
        if not m:
            continue
        sem, label = m.group(1), m.group(2)
        label = re.sub(r'\(\s*(all|both) majors?\s*\)', '', label, flags=re.I)
        label = re.sub(r'^core\s+', '', label, flags=re.I)
        label = re.sub(r'\s*-\s*core$', '', label, flags=re.I)
        label = norm(label).upper()
        parts = [p.strip() for p in re.split(r'\s*/\s*|\s+&\s+', label)]
        if len(parts) > 1 and all(p in PROGRAMMES for p in parts):
            out += [(sem, p) for p in parts]
        else:
            out.append((sem, label))
    return out


def read(path):
    wb = load_workbook(path, data_only=True)
    courses = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        header = rows[2]
        c = {'code': column(header, 'Course Code'), 'name': column(header, 'Course Name'), 'offered': column(header, 'Offered to'),
             'hours': column(header, 'Course hours'), 'intake': column(header, 'Intake'), 'adv': column(header, 'Adv.'),
             'other': column(header, 'other Fac.'), 'lg': column(header, 'No. of Lecture Groups'), 'tg': column(header, 'No. of Tuts/Labs Groups'),
             'lecturer': column(header, 'Lecturer', exact=True), 'tas': column(header, 'TAs', exact=True, last=True)}
        current = None
        for row in rows[4:]:
            get = lambda k: row[c[k]] if c[k] is not None and c[k] < len(row) else None
            code, name, offered = norm(get('code')), norm(get('name')), get('offered')
            lecturer = norm(get('lecturer'))
            if not code and not (name and offered):
                if current and lecturer and lecturer.lower() not in ('none',):
                    current['lecturers'].append(lecturer)  # an extra lecturer of the course above
                continue
            L, E, P = (number(row[c['hours'] + i]) for i in range(3))
            sup = re.match(r'supervised by\s+(.*)', lecturer, re.I)
            lecturers = [] if (not lecturer or lecturer.lower() == 'none' or 'n.n' in lecturer.lower() or (sup and not L)) else [sup.group(1) if sup else lecturer]
            current = {'sheet': ws.title, 'code': code, 'name': name or code, 'offered': norm(offered), 'cohorts': cohorts_of(offered),
                       'L': L, 'E': E, 'P': P, 'students': int(number(get('intake')) + number(get('adv')) + number(get('other'))),
                       'lg': int(number(get('lg'))), 'tg': int(number(get('tg'))), 'lecturers': lecturers,
                       'tas': math.ceil(number(get('tas')) - 1e-9) if number(get('tas')) > 0 else 0}
            courses.append(current)
    return courses


def plan(courses):
    """Student groups per cohort, and the activities of every course."""
    need, students = defaultdict(int), defaultdict(int)
    for c in courses:
        k = len(c['cohorts']) or 1
        for co in c['cohorts']:
            need[co] = max(need[co], math.ceil(c['tg'] / k) if c['tg'] else 1)
            students[co] = max(students[co], math.ceil(c['students'] / k))
    groups, used = {}, set()
    for (sem, label), n in sorted(need.items()):
        size = max(1, math.ceil((students[(sem, label)] or 25 * n) / n))
        words = re.findall(r'[A-Z]+', label)
        abbr = (words[0][:6] if len(words) == 1 else ''.join(w[0] for w in words)[:6]) or 'X'
        while f'{abbr}{sem}' in used:  # "6th BA - FA" and "6th BA - Finance" must not share codes
            abbr = abbr[:5] + str(len([u for u in used if u.startswith(abbr[:5])]) + 1)
        used.add(f'{abbr}{sem}')
        groups[(sem, label)] = [{'code': f'{abbr}{sem}-G{i + 1}', 'name': f'{label.title()} sem {sem} G{i + 1}', 'size': size,
                                 'year': (int(sem) + 1) // 2, 'major': label.title()} for i in range(n)]
    acts, codes = [], Counter()
    for idx, c in enumerate(courses):
        base = re.sub(r'\s+', '', c['code']) or f"{c['sheet'][:4].upper()}{idx}"
        codes[base] += 1
        if codes[base] > 1:
            base = f'{base}~{codes[base]}'
        c['key'] = base
        pool = [g for co in c['cohorts'] for g in groups[co]]
        chunks = lambda n: [pool[round(i * len(pool) / n):round((i + 1) * len(pool) / n)] for i in range(n)] if n and pool else []
        for kind, hours, n, tag in (('lecture', c['L'], max(c['lg'], 1) if c['L'] else 0, 'L'), ('tutorial', c['E'], c['tg'], 'T'), ('lab', c['P'], c['tg'], 'P')):
            if not hours or not n:
                continue
            for i, members in enumerate(chunks(min(n, len(pool)))):
                acts.append({'course': c, 'kind': kind, 'code': f'{base}-{tag}{i + 1}'[:20], 'groups': members, 'sessions': sessions_for(hours),
                             'planned_minutes': int(hours * 60)})
    return groups, acts


class Api:
    def __init__(self, base):
        import httpx
        self.c = httpx.Client(base_url=base.rstrip('/') + '/api', headers={'X-Jadwai-Request': '1'}, timeout=300)
        self.c.post('/auth/login', json={'email': os.environ['JADWAI_EMAIL'], 'password': os.environ['JADWAI_PASSWORD']}).raise_for_status()
        self.version = self.get('/workspace')['version']

    def get(self, path):
        r = self.c.get(path); r.raise_for_status(); return r.json()

    def write(self, method, path, body=None):
        r = self.c.request(method, path, json=body, headers={'If-Match': f'"{self.version}"'})
        if r.status_code >= 400:
            sys.exit(f'{method} {path} -> {r.status_code} {r.text[:300]}')
        data = r.json() if r.content else {}
        self.version = data['version'] if isinstance(data, dict) and 'version' in data else self.get('/workspace')['version']
        return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('workbook'); ap.add_argument('--rooms', required=True); ap.add_argument('--term', default='Spring 2024 (staff planning)')
    ap.add_argument('--commit', action='store_true'); ap.add_argument('--clear', action='store_true')
    # Placeholder rooms when the room list is too small for the plan; clearly named so they are never mistaken for real ones.
    ap.add_argument('--extra-halls', type=int, default=0); ap.add_argument('--extra-labs', type=int, default=0); ap.add_argument('--extra-big-labs', type=int, default=0)
    args = ap.parse_args()
    courses = read(args.workbook)
    groups, acts = plan(courses)
    setup = json.load(open(args.rooms))
    rooms = list(setup['rooms'])
    rooms += [{'name': f'Extra hall {i + 1} (placeholder)', 'code': f'XH{i + 1}', 'capacity': 260, 'room_type': 'lecture', 'room_types': ['lecture', 'exam_hall'], 'equipment': ['Projector']} for i in range(args.extra_halls)]
    rooms += [{'name': f'Extra lab {i + 1} (placeholder)', 'code': f'XL{i + 1}', 'capacity': 40, 'room_type': 'lab', 'room_types': ['lab'], 'equipment': []} for i in range(args.extra_labs)]
    rooms += [{'name': f'Extra large lab {i + 1} (placeholder)', 'code': f'XLL{i + 1}', 'capacity': 80, 'room_type': 'lab', 'room_types': ['lab'], 'equipment': []} for i in range(args.extra_big_labs)]
    planned = sum(a['planned_minutes'] * len(a['groups'] and [1]) for a in acts)
    by_kind = Counter(a['kind'] for a in acts for _ in range(a['sessions']))
    big = sum(a['sessions'] for a in acts if a['kind'] == 'lecture' and sum(g['size'] for g in a['groups']) > 35)
    halls = sum(1 for r in rooms if r['capacity'] >= 100)
    labs = sum(1 for r in rooms if 'lab' in (r.get('room_types') or [r.get('room_type')]))
    slots = len(setup['calendar']['days']) * len(setup['calendar']['teaching_periods'])
    print(f"{len(courses)} courses, {sum(len(v) for v in groups.values())} student groups in {len(groups)} cohorts, {len(acts)} activities")
    print(f"weekly sessions: {sum(by_kind.values())} ({dict(by_kind)}); planned {sum(a['planned_minutes'] for a in acts)} min, "
          f"scheduled {sum(a['sessions'] * 90 for a in acts)} min")
    print(f"lecture sessions needing more than 35 seats: {big}; halls with 100+ seats: {halls} x {slots} slots = {halls * slots}")
    print(f"lab sessions: {by_kind['lab']}; labs: {labs} x {slots} slots = {labs * slots}")
    staff = Counter(l for c in courses for l in c['lecturers'])
    print(f"named lecturers: {len(staff)}; courses with a placeholder lecturer: {sum(1 for c in courses if c['L'] and not c['lecturers'])}; "
          f"placeholder TAs: {sum(c['tas'] or (1 if (c['E'] or c['P']) and c['tg'] else 0) for c in courses)}")
    if not args.commit:
        return
    api = Api(os.environ.get('JADWAI_URL', 'http://127.0.0.1:8012'))
    if args.clear:
        for rule in api.get('/workspace')['rules']:
            if rule['status'] == 'approved':
                api.write('POST', f"/rules/{rule['id']}/revoke")
            api.write('DELETE', f"/rules/{rule['id']}")
        for kind in ('courses', 'instructors', 'rooms', 'groups'):
            for record in [r for r in api.get('/workspace')['records'] if r['kind'] == kind]:
                api.write('DELETE', f"/records/{kind}/{record['id']}")
    if api.get('/workspace')['records']:
        sys.exit('This workspace already has records. Load into an empty workspace (or pass --clear on a copy meant for this data).')
    cal = setup['calendar']
    api.write('PUT', '/workspace', {'name': 'German International University', 'term': args.term, 'timezone': cal.get('timezone') or 'Africa/Cairo',
              'days': cal['days'], 'start_hour': cal['start_hour'], 'end_hour': cal['end_hour'], 'teaching_periods': cal['teaching_periods'],
              'period_minutes': cal.get('period_minutes') or 30, 'start_date': None, 'end_date': None, 'realism_policy': cal.get('realism_policy') or {}})
    for r in rooms:
        api.write('POST', '/records/rooms', {k: r[k] for k in ('name', 'code', 'capacity', 'room_type', 'room_types', 'equipment')})
    gid = {}
    for cohort, members in groups.items():
        for g in members:
            gid[g['code']] = api.write('POST', '/records/groups', g)['id']
    people, n = {}, 0

    def person(name, sheet, position, code=None):
        nonlocal n
        if name not in people:
            n += 1
            people[name] = api.write('POST', '/records/instructors', {'name': name[:100], 'code': code or f'S{n:03d}', 'department': sheet, 'position': position})['id']
        return people[name]
    for c in courses:
        if not any(a['course'] is c for a in acts):
            print(f"{c['sheet']}: {c['key']} {c['name'][:40]} skipped: no students or groups planned", flush=True)
            continue
        lecturers = [person(l, c['sheet'], 'doctor') for l in c['lecturers']] or ([person(f"N.N. ({c['key']})", c['sheet'], 'doctor', f"NN-{c['key']}"[:20])] if c['L'] else [])
        count = c['tas'] or (1 if (c['E'] or c['P']) and c['tg'] else 0)
        tas = [person(f"{c['key']} TA {i + 1}", c['sheet'], 'ta', f"TA-{c['key']}-{i + 1}"[:20]) for i in range(count)]
        members = sorted({gid[g['code']] for a in acts if a['course'] is c for g in a['groups']})
        course_id = api.write('POST', '/course-catalog', {'name': c['name'][:100], 'code': c['key'][:20], 'group_ids': members,
                              'eligibility': {'lecture': lecturers, 'tutorial': tas if c['E'] else [], 'lab': tas if c['P'] else []}})['id']
        for a in (a for a in acts if a['course'] is c):
            api.write('POST', '/records/courses', {'course_id': course_id, 'name': c['name'][:100], 'code': a['code'], 'activity_type': a['kind'],
                      'sessions': a['sessions'], 'duration': 90, 'eligible_instructors': lecturers if a['kind'] == 'lecture' else tas,
                      'group_ids': [gid[g['code']] for g in a['groups']], 'required_equipment': []})
        print(f"{c['sheet']}: {c['key']} {c['name'][:40]}", flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
