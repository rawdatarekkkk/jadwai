"""Load a realistic multi-faculty demo semester into a JadwAI workspace through its HTTP API.

Structure follows GIU-WINTER 26-schedule-V7.xlsx (sections, streams, tutorial-group
ranges, courses, room codes) and course codes from the Winter 2026 midterm schedule.
Room capacities/types, staff names, group sizes and days off are not in those files;
they are realistic placeholders, labelled as demo data. Use only on a demo database.

    JADWAI_URL=http://127.0.0.1:8011 JADWAI_EMAIL=... JADWAI_PASSWORD=... python scripts/load_university_demo.py [--clear]

JADWAI_ROOM_CODES may hold a JSON list of further room codes (e.g. the workbook's) to add as tutorial rooms.
"""
import os
import random
import sys
import uuid
import httpx

BASE = os.environ.get('JADWAI_URL', 'http://127.0.0.1:8011').rstrip('/') + '/api'
random.seed(2026)
GROUP_SIZE = 25
DAYS = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
PERIODS = [{'start': s, 'end': e} for s, e in [(510, 600), (615, 705), (720, 810), (825, 915), (945, 1035)]]

# Rooms from the workbook. Types/capacities are demo assumptions by building block.
HALLS = ['A.020', 'A3.020', 'M.045', 'A3.128', 'A3.228', 'A3.328', 'A3.428', 'A3.429']
LABS = ['TC01', 'TC03', 'TC05', 'TC10', 'TC13', 'TC18', 'TC19', 'C-206', 'C-207', 'I.324', 'C.101', 'C.102']
SPECIAL = {'I.423': ['Data Science Lab', 'GPU'], 'I.323': ['Security Lab'], 'C.201': ['Electronics Lab']}

# section -> (faculty, programme, semester, streams [(name, groups)], courses)
# course: (code, name, kind, needs) where kind is the per-group activity ('tutorial' | 'lab').
SECTIONS = [
    ('INF1', 'Informatics and Computer Science', 'Applied Computer Science & Informatics', 1,
     [('I', 9), ('II', 8), ('III', 8)],
     [('CSEN101', 'Math I', 'tutorial', ()), ('CSEN102', 'Programming I', 'lab', ()),
      ('CSEN103', 'Digital Logic Design', 'tutorial', ()), ('CSEN104', 'Physics', 'tutorial', ())]),
    ('INF3', 'Informatics and Computer Science', 'Applied Computer Science & Informatics', 3,
     [('I', 6), ('II', 6), ('III', 6)],
     [('INCS101', 'Programming III', 'tutorial', ()), ('INCS103', 'Data Structures & Algorithms', 'lab', ()),
      ('INCS104', 'Databases', 'lab', ()), ('INCS105', 'Math III', 'tutorial', ()), ('INCS102', 'Operating Systems', 'lab', ())]),
    ('INF5-DS', 'Informatics and Computer Science', 'Data Science', 5, [('DS', 4)],
     [('ICS504', 'Machine Learning', 'lab', ('Data Science Lab',)), ('ICS506', 'Data Engineering & Visualization', 'lab', ('Data Science Lab',)),
      ('ICS502', 'Database Programming', 'lab', ())]),
    ('INF5-SEC', 'Informatics and Computer Science', 'IT Security', 5, [('SEC', 3)],
     [('ICS507', 'Digital Forensics', 'lab', ('Security Lab',)), ('ICS505', 'Cryptography', 'lab', ('Security Lab',)),
      ('ICS508', 'Software & Mobile Devices', 'lab', ())]),
    ('INF5-SE', 'Informatics and Computer Science', 'Software Engineering', 5, [('SE', 3)],
     [('ICS510', 'Software Design & Architecture', 'lab', ()), ('ICS511', 'Software Construction & Testing', 'lab', ()),
      ('ICS512', 'Requirements Engineering', 'tutorial', ())]),
    ('BI3', 'Business Informatics', 'Business Informatics', 3, [('I', 8), ('II', 8)],
     [('BINF303', 'Data Structures & Algorithms for BI', 'lab', ()), ('BINF302', 'Enterprise System Applications', 'tutorial', ()),
      ('BINF301', 'Information & Communication Architecture', 'tutorial', ()), ('BUAD301', 'Management Accounting for BI', 'tutorial', ()),
      ('BINF304', 'Math III - Probability & Statistics', 'tutorial', ())]),
    ('BI5', 'Business Informatics', 'Business Informatics', 5, [('I', 5), ('II', 4)],
     [('BINF503', 'Electronic Business Development', 'lab', ()), ('BINF502', 'Auditing Analytics', 'lab', ()),
      ('BINF504', 'AI in Business', 'lab', ('Data Science Lab',)), ('BUAD520', 'Operations Management', 'tutorial', ()),
      ('BUAD519', 'Financial Technologies', 'tutorial', ())]),
    ('BA5', 'Business Administration', 'Business Administration', 5, [('Core', 10)],
     [('BSAD502', 'Project Management', 'tutorial', ()), ('BSAD501', 'Management Accounting', 'tutorial', ()),
      ('BSAD503', 'Research Methodology', 'tutorial', ())]),
    ('BA5-DM', 'Business Administration', 'Digital Marketing', 5, [('DM', 3)],
     [('BSDM501', 'Social Media Management', 'tutorial', ()), ('BSDM502', 'Marketing Analytics', 'tutorial', ())]),
    ('BA5-FBA', 'Business Administration', 'Finance, Banking & Accounting', 5, [('FBA', 2)],
     [('BSFA501', 'International Accounting', 'tutorial', ()), ('BSFA502', 'Capital Markets', 'tutorial', ())]),
]
FIRST = ['Ahmed', 'Mohamed', 'Omar', 'Youssef', 'Karim', 'Mostafa', 'Hassan', 'Tarek', 'Amr', 'Hany', 'Sherif', 'Khaled', 'Mahmoud', 'Ali', 'Ibrahim',
         'Sara', 'Mona', 'Nour', 'Salma', 'Yasmin', 'Hana', 'Mariam', 'Laila', 'Dina', 'Rana', 'Nada', 'Reem', 'Farida', 'Habiba', 'Malak']
LAST = ['Hassan', 'Adel', 'Samy', 'Nabil', 'Fawzy', 'Tarek', 'Mansour', 'Saleh', 'Gamal', 'Ezzat', 'Ragab', 'Shawky', 'Hamdy', 'Lotfy', 'Fahmy', 'Kamel', 'Zaki', 'Osman', 'Helmy', 'Sobhy']


class Api:
    def __init__(self):
        self.c = httpx.Client(base_url=BASE, headers={'X-Jadwai-Request': '1'}, timeout=300)
        r = self.c.post('/auth/login', json={'email': os.environ['JADWAI_EMAIL'], 'password': os.environ['JADWAI_PASSWORD']})
        r.raise_for_status()
        self.version = self.get('/workspace')['version']

    def get(self, path):
        r = self.c.get(path); r.raise_for_status(); return r.json()

    def write(self, method, path, body=None):
        r = self.c.request(method, path, json=body, headers={'If-Match': f'"{self.version}"'})
        if r.status_code >= 400:
            sys.exit(f'{method} {path} -> {r.status_code} {r.text[:300]}')
        data = r.json() if r.content else {}
        if isinstance(data, dict) and 'version' in data:
            self.version = data['version']
        else:  # 204 responses and some actions do not echo the new version
            self.version = self.get('/workspace')['version']
        return data


def names(count, used, title=''):
    out = []
    while len(out) < count:
        name = f'{title}{random.choice(FIRST)} {random.choice(LAST)}'
        if name not in used:
            used.add(name); out.append(name)
    return out


def main():
    api = Api()
    if '--clear' in sys.argv:
        # Remove the seed's small sample semester (demo databases only).
        for rule in api.get('/workspace')['rules']:
            if rule['status'] == 'approved':
                api.write('POST', f"/rules/{rule['id']}/revoke")
            api.write('DELETE', f"/rules/{rule['id']}")
        for kind in ('courses', 'instructors', 'rooms', 'groups'):
            for record in [r for r in api.get('/workspace')['records'] if r['kind'] == kind]:
                api.write('DELETE', f"/records/{kind}/{record['id']}")
    if api.get('/workspace')['records']:
        sys.exit('This workspace already has academic records. Load the demo into an empty demo database (or pass --clear on a demo database).')
    api.write('PUT', '/workspace', {'name': 'German International University', 'term': 'Winter 2026 [Demo]', 'timezone': 'Africa/Cairo',
              'days': DAYS, 'start_hour': 8, 'end_hour': 18, 'teaching_periods': PERIODS, 'period_minutes': 30,
              'start_date': None, 'end_date': None, 'realism_policy': {'max_consecutive_periods': 4, 'student_daily_hours': 7.5}})
    room = lambda code, cap, types, eq=(): api.write('POST', '/records/rooms', {'name': code, 'code': code, 'capacity': cap, 'room_types': list(types), 'room_type': types[0], 'equipment': list(eq)})['id']
    for code in HALLS:
        room(code, 260, ['lecture', 'exam_hall'], ['Projector'])
    for code in LABS:
        room(code, 30, ['lab'], ['Computers'])
    for code, features in SPECIAL.items():
        room(code, 30, ['lab'], ['Computers', *features])
    used_rooms = set(HALLS) | set(LABS) | set(SPECIAL)
    import json
    workbook_rooms = json.loads(os.environ.get('JADWAI_ROOM_CODES', '[]'))
    for code in [c for c in workbook_rooms if c not in used_rooms]:
        room(code, 35, ['lecture'], ['Projector'])
    staff_names = set()
    total = 0
    for key, faculty, programme, semester, streams, courses in SECTIONS:
        year = (semester + 1) // 2
        groups, by_stream, number = {}, {}, 1
        for stream, count in streams:
            by_stream[stream] = []
            for _ in range(count):
                code = f'{key}-G{number}'
                gid = api.write('POST', '/records/groups', {'name': f'{programme} {stream} G{number}', 'code': code, 'size': GROUP_SIZE, 'year': year, 'major': programme})['id']
                groups[code] = gid; by_stream[stream].append(gid); number += 1
        all_groups = list(groups.values())
        for code, name, kind, needs in courses:
            doctor_name, = names(1, staff_names, 'Dr. ')
            doctor = api.write('POST', '/records/instructors', {'name': doctor_name, 'code': f'D-{code}', 'department': faculty, 'position': 'doctor', 'day_off': random.choice(DAYS)})['id']
            ta_count = max(2, min(4, len(all_groups) // 5))
            tas = [api.write('POST', '/records/instructors', {'name': n, 'code': f'T-{code}-{i + 1}', 'department': faculty, 'position': 'ta', 'day_off': random.choice(DAYS)})['id']
                   for i, n in enumerate(names(ta_count, staff_names))]
            course_id = api.write('POST', '/course-catalog', {'name': name, 'code': code, 'group_ids': all_groups,
                                  'eligibility': {'lecture': [doctor], 'tutorial': tas if kind == 'tutorial' else [], 'lab': tas if kind == 'lab' else []}})['id']
            for stream, ids in by_stream.items():
                api.write('POST', '/records/courses', {'course_id': course_id, 'name': name, 'code': f'{code}-L-{stream}'[:20], 'activity_type': 'lecture', 'sessions': 1, 'duration': 90,
                          'eligible_instructors': [doctor], 'group_ids': ids, 'required_equipment': []})
                total += 1
            for gcode, gid in groups.items():
                api.write('POST', '/records/courses', {'course_id': course_id, 'name': name, 'code': f'{code}-{gcode.split("-")[-1]}'[:20], 'activity_type': kind, 'sessions': 1, 'duration': 90,
                          'eligible_instructors': tas, 'group_ids': [gid], 'required_equipment': list(needs) if kind == 'lab' else []})
                total += 1
        print(f'{key}: {len(groups)} groups, {len(courses)} courses', flush=True)
    print(f'{total} weekly sessions', flush=True)


if __name__ == '__main__':
    main()
