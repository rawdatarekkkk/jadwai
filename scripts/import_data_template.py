"""Check and import a filled-in JadwAI data-entry workbook (see make_data_template.py).

Every row is checked first; any problem is reported by sheet and row and nothing is
written. With --commit, a JSON backup of the workspace is saved, then the data is loaded
through the HTTP API, so the website's own validation applies to every record:
existing rooms and catalogue courses (matched by code) are updated, everything else is added.

    cd backend && set -a && source ../.env && set +a
    .venv/bin/python ../scripts/import_data_template.py filled.xlsx            # check only
    .venv/bin/python ../scripts/import_data_template.py filled.xlsx --commit   # check, back up, import
Environment: JADWAI_URL (default http://127.0.0.1:8010), JADWAI_EMAIL, JADWAI_PASSWORD.
"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from openpyxl import load_workbook  # noqa: E402

USES = {'lecture', 'lab', 'flexible', 'exam_hall'}
DAYS = {'Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'}
SHORT = {'Informatics and Computer Science': 'INF', 'Business Informatics': 'BI', 'Business Administration': 'BA', 'Engineering': 'ENG',
         'Biotechnology': 'BIO', 'Pharmaceutical Engineering': 'PHE', 'Architecture': 'ARC', 'Physical Therapy': 'PT'}


def split(value):
    return [v.strip() for v in str(value or '').split('|') if v.strip()]


def rows(wb, sheet):
    """(Excel row number, {header: value}) for filled rows, skipping the example row."""
    ws = wb[sheet]
    headers = [c.value for c in ws[1]]
    for number, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        data = dict(zip(headers, values))
        if str(data.get('Code') or '').upper() == 'EXAMPLE' or number == 2:
            continue
        if any(v not in (None, '') for k, v in data.items() if k not in ('Check', 'Workbook blocks')):
            yield number, data


def whole(value, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high and float(value) == number else None


def check(path, calendar):
    """Return (plan, problems)."""
    from app.calendar_slots import day_placements
    wb = load_workbook(path, data_only=True)
    problems = []
    bad = lambda sheet, number, message: problems.append(f'{sheet} row {number}: {message}')
    rooms, staff, groups, courses = {}, {}, {}, []
    for n, r in rows(wb, 'Rooms'):
        code, uses = str(r['Code'] or '').strip(), split(r['Uses'])
        capacity = whole(r['Capacity'], 1, 2000)
        if not code: bad('Rooms', n, 'code missing')
        if capacity is None: bad('Rooms', n, 'capacity must be a whole number from 1 to 2000')
        if not uses or set(uses) - USES: bad('Rooms', n, 'uses must be from lecture, lab, flexible, exam_hall')
        if code in rooms: bad('Rooms', n, f'room {code} appears twice')
        rooms[code] = {'name': str(r['Name'] or code).strip(), 'code': code, 'capacity': capacity, 'room_types': uses, 'room_type': uses[0] if uses else None, 'equipment': split(r['Features'])}
    for n, r in rows(wb, 'Staff'):
        code = str(r['Code'] or '').strip()
        position = str(r['Position'] or '').strip().lower()
        if not code or not r['Name'] or not r['Department']: bad('Staff', n, 'code, name and department are required')
        if position not in ('doctor', 'ta'): bad('Staff', n, 'position must be doctor or ta')
        if r['Day off'] not in DAYS: bad('Staff', n, 'day off must be a weekday name')
        if code in staff: bad('Staff', n, f'staff code {code} appears twice')
        if len(code) > 20: bad('Staff', n, 'code must be at most 20 characters')
        staff[code] = {'name': str(r['Name'] or '').strip(), 'code': code, 'department': str(r['Department'] or '').strip(), 'position': position, 'day_off': r['Day off']}
    streams = defaultdict(list)
    for n, r in rows(wb, 'Groups'):
        code, size, semester = str(r['Code'] or '').strip(), whole(r['Students'], 1, 2000), whole(r['Semester'], 1, 12)
        if not code: bad('Groups', n, 'code missing')
        if size is None: bad('Groups', n, 'students must be a whole number from 1 to 2000')
        if semester is None: bad('Groups', n, 'semester missing')
        if code in groups: bad('Groups', n, f'group {code} appears twice')
        groups[code] = {'name': f"{r['Programme']} {r['Stream']} G{r['Group']}"[:100], 'code': code, 'size': size, 'year': whole(r['Year'], 1, 12), 'major': str(r['Programme'] or '')[:100] or None}
        streams[(r['Programme'], semester, str(r['Stream'] or '').strip())].append(code)
    lab_features = set().union(*[set(r['equipment']) for r in rooms.values() if 'lab' in r['room_types']] or [set()])
    teaching_tas = set()
    for n, r in rows(wb, 'Courses'):
        code, semester = str(r['Code'] or '').strip(), whole(r['Semester'], 1, 12)
        counts = {k: whole(r[h] or 0, 0, 10) for k, h in (('lecture', 'Lectures/week'), ('tutorial', 'Tutorials/week'), ('lab', 'Labs/week'))}
        minutes = whole(r['Minutes'] or 90, 30, 240)
        doctors, tas, features = split(r['Doctors']), split(r['TAs']), split(r['Room features'])
        names = split(r['Streams'])
        if not code: bad('Courses', n, 'course code missing'); continue
        if len(code) > 15: bad('Courses', n, 'course code must be at most 15 characters')
        if None in counts.values(): bad('Courses', n, 'sessions per week must be whole numbers from 0 to 10')
        if minutes is None or not day_placements(calendar, minutes): bad('Courses', n, f'{r["Minutes"]} minutes does not fit the teaching periods')
        missing = [s for s in names if (r['Programme'], semester, s) not in streams]
        if not names or missing: bad('Courses', n, f'unknown stream(s): {", ".join(missing) or "none given"}')
        if counts['lecture'] and not doctors: bad('Courses', n, 'lectures need at least one doctor')
        if (counts['tutorial'] or counts['lab']) and not tas: bad('Courses', n, 'tutorials and labs need at least one TA')
        for c in doctors:
            if staff.get(c, {}).get('position') != 'doctor': bad('Courses', n, f'{c} is not a doctor on the Staff sheet')
        for c in tas:
            if staff.get(c, {}).get('position') != 'ta': bad('Courses', n, f'{c} is not a TA on the Staff sheet')
        if counts['lab'] and features and not set(features) <= lab_features:
            bad('Courses', n, f'no lab room has all of: {", ".join(features)}')
        if counts['tutorial'] or counts['lab']:
            teaching_tas.update(tas)
        courses.append({'row': n, 'code': code, 'name': str(r['Name'] or code).strip()[:100], 'counts': counts, 'minutes': minutes, 'doctors': doctors,
                        'tas': tas, 'features': features, 'streams': {s: streams.get((r['Programme'], semester, s), []) for s in names},
                        'tag': f"{SHORT.get(r['Programme'], 'X')}{semester}", 'expected': whole(r['Expected students'], 1, 5000)})
    for code, person in staff.items():
        if person['position'] == 'ta' and code not in teaching_tas:
            problems.append(f'Staff: TA {code} ({person["name"]}) is not listed for any tutorial or lab. Every TA must teach.')
    advising = advising_rows(wb, groups, courses, bad)
    return {'rooms': rooms, 'staff': staff, 'groups': groups, 'courses': courses, 'advising': advising}, problems


def advising_rows(wb, groups, courses, bad):
    """Advising students: a home group plus courses dropped and courses taken with another group.

    Optional sheet (older workbooks have none). Drop: course codes. Add: COURSE@GROUP, the group
    whose sessions the student joins."""
    if 'Advising students' not in wb.sheetnames:
        return []
    taught = defaultdict(set)  # course code -> group codes that take it
    for c in courses:
        for codes in c['streams'].values():
            taught[c['code']].update(codes)
    found, seen = [], set()
    for n, r in rows(wb, 'Advising students'):
        code, home = str(r['Code'] or '').strip(), str(r['Home group'] or '').strip()
        name = str(r['Name'] or '').strip()
        drops = split(r['Drop courses'])
        adds = [tuple(x.split('@', 1)) if '@' in x else (x, '') for x in split(r['Add courses'])]
        if not code or not name: bad('Advising students', n, 'code and name are required'); continue
        if len(code) > 20: bad('Advising students', n, 'code must be at most 20 characters')
        if code.casefold() in seen: bad('Advising students', n, f'student {code} appears twice')
        seen.add(code.casefold())
        if home not in groups: bad('Advising students', n, f'home group {home or "(empty)"} is not on the Groups sheet'); continue
        if not drops and not adds: bad('Advising students', n, 'list at least one dropped or added course')
        if len(drops) + len(adds) > 30: bad('Advising students', n, 'at most 30 course changes')
        for course in drops:
            if course not in taught: bad('Advising students', n, f'dropped course {course} is not on the Courses sheet')
            elif home not in taught[course]: bad('Advising students', n, f'{home} does not take {course}, so it cannot be dropped')
        for course, group in adds:
            if not group: bad('Advising students', n, f'write the added course as COURSE@GROUP ({course}@...)')
            elif course not in taught: bad('Advising students', n, f'added course {course} is not on the Courses sheet')
            elif group not in groups: bad('Advising students', n, f'group {group} is not on the Groups sheet')
            elif group not in taught[course]: bad('Advising students', n, f'{group} does not take {course}')
            elif home in taught[course] and course not in drops: bad('Advising students', n, f'{home} already takes {course}; drop it too to take it with {group}')
        if len({c for c, _ in adds}) < len(adds) or len(set(drops)) < len(drops): bad('Advising students', n, 'a course is listed twice')
        found.append({'row': n, 'code': code, 'name': name[:100], 'home': home, 'drops': drops, 'adds': [a for a in adds if a[1]]})
    return found


class Api:
    def __init__(self):
        import httpx
        self.c = httpx.Client(base_url=os.environ.get('JADWAI_URL', 'http://127.0.0.1:8010').rstrip('/') + '/api', headers={'X-Jadwai-Request': '1'}, timeout=120)
        self.c.post('/auth/login', json={'email': os.environ['JADWAI_EMAIL'], 'password': os.environ['JADWAI_PASSWORD']}).raise_for_status()
        self.version = self.get('/workspace')['version']

    def get(self, path):
        r = self.c.get(path); r.raise_for_status(); return r.json()

    def write(self, method, path, body, what):
        r = self.c.request(method, path, json=body, headers={'If-Match': f'"{self.version}"'})
        if r.status_code >= 400:
            sys.exit(f'Stopped at {what}: {r.status_code} {r.text[:200]}. Records written before this point remain; the backup is in backups/.')
        data = r.json() if r.content else {}
        self.version = data['version'] if isinstance(data, dict) and 'version' in data else self.get('/workspace')['version']
        return data


def commit(plan, api):
    ws = api.get('/workspace')
    backups = Path(__file__).resolve().parents[1] / 'backups'
    backups.mkdir(mode=0o700, exist_ok=True)
    backup = backups / f'before-data-import-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json'
    backup.write_text(json.dumps(ws, ensure_ascii=False, indent=1)); backup.chmod(0o600)
    existing = {(r['kind'], r['code'].casefold()): r for r in ws['records']}
    catalog = {c['code'].casefold(): c for c in ws.get('course_catalog') or []}
    ids = {}
    for kind, items in (('rooms', plan['rooms']), ('instructors', plan['staff']), ('groups', plan['groups'])):
        for code, body in items.items():
            current = existing.get((kind, code.casefold()))
            if current:
                api.write('PUT', f'/records/{kind}/{current["id"]}', body, f'{kind} {code}'); ids[code] = current['id']
            else:
                ids[code] = api.write('POST', f'/records/{kind}', body, f'{kind} {code}')['id']
    by_code, course_ids = defaultdict(list), {}
    for course in plan['courses']:
        by_code[course['code']].append(course)
    made = 0
    for code, rows_ in by_code.items():
        eligibility = {'lecture': set(), 'tutorial': set(), 'lab': set()}
        groups = set()
        for c in rows_:
            if c['counts']['lecture']: eligibility['lecture'].update(ids[d] for d in c['doctors'])
            for kind in ('tutorial', 'lab'):
                if c['counts'][kind]: eligibility[kind].update(ids[t] for t in c['tas'])
            groups.update(ids[g] for codes in c['streams'].values() for g in codes)
        body = {'name': rows_[0]['name'], 'code': code, 'group_ids': sorted(groups), 'eligibility': {k: sorted(v) for k, v in eligibility.items()},
                'expected_students': next((c['expected'] for c in rows_ if c['expected']), None)}
        current = catalog.get(code.casefold())
        course_id = api.write('PUT', f'/course-catalog/{current["id"]}', {**body, 'name': current['name']}, f'course {code}')['id'] if current else api.write('POST', '/course-catalog', body, f'course {code}')['id']
        course_ids[code] = course_id
        for c in rows_:
            for stream, codes in c['streams'].items():
                if c['counts']['lecture']:
                    made += 1
                    api.write('POST', '/records/courses', {'course_id': course_id, 'name': c['name'], 'code': f'{code[:12]}-A{made}', 'activity_type': 'lecture',
                              'sessions': c['counts']['lecture'], 'duration': c['minutes'], 'eligible_instructors': [ids[d] for d in c['doctors']],
                              'group_ids': [ids[g] for g in codes], 'required_equipment': []}, f'{code} lecture ({stream})')
                for kind in ('tutorial', 'lab'):
                    for g in codes if c['counts'][kind] else []:
                        made += 1
                        api.write('POST', '/records/courses', {'course_id': course_id, 'name': c['name'], 'code': f'{code[:12]}-A{made}', 'activity_type': kind,
                                  'sessions': c['counts'][kind], 'duration': c['minutes'], 'eligible_instructors': [ids[t] for t in c['tas']],
                                  'group_ids': [ids[g]], 'required_equipment': c['features'] if kind == 'lab' else []}, f'{code} {kind} ({g})')
    students = commit_advising(plan.get('advising', []), ids, course_ids, api)
    print(f'Imported {len(plan["rooms"])} rooms, {len(plan["staff"])} staff, {len(plan["groups"])} groups, {len(by_code)} courses, {made} activities, {students} advising students. Backup: {backup}')


def commit_advising(students, ids, course_ids, api):
    """Create or update advising students (matched by code) after their groups and courses exist."""
    if not students:
        return 0
    existing = {s['code'].casefold(): s for s in api.get('/advising-students')['students']}
    for s in students:
        body = {'code': s['code'], 'name': s['name'], 'group_id': ids[s['home']],
                'changes': [{'action': 'drop', 'course_id': course_ids[c], 'group_id': None} for c in s['drops']]
                           + [{'action': 'add', 'course_id': course_ids[c], 'group_id': ids[g]} for c, g in s['adds']]}
        current = existing.get(s['code'].casefold())
        if current:
            api.write('PUT', f'/advising-students/{current["id"]}', body, f'advising student {s["code"]}')
        else:
            api.write('POST', '/advising-students', body, f'advising student {s["code"]}')
    return len(students)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    # Check against the calendar of the workspace being imported into.
    api = Api()
    plan, problems = check(sys.argv[1], api.get('/workspace')['calendar'])
    if problems:
        print(f'{len(problems)} problem(s); nothing was imported:')
        print('\n'.join('  ' + p for p in problems[:200]))
        sys.exit(1)
    sessions = sum((c['counts']['lecture'] * len(c['streams'])) + sum(c['counts'][k] * sum(len(v) for v in c['streams'].values()) for k in ('tutorial', 'lab')) for c in plan['courses'])
    print(f'OK: {len(plan["rooms"])} rooms, {len(plan["staff"])} staff, {len(plan["groups"])} groups, {len(plan["courses"])} course rows, {sessions} weekly sessions, {len(plan["advising"])} advising students.')
    if '--commit' in sys.argv:
        commit(plan, api)


if __name__ == '__main__':
    main()
