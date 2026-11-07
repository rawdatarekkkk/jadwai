"""Add demo advising students (retakes, section changes, cross-programme courses) through the API.

    JADWAI_URL=http://127.0.0.1:8011 JADWAI_EMAIL=... JADWAI_PASSWORD=... python scripts/load_advising_demo.py [--count 60] [--clear]

Names and IDs are invented (DEMO-...). Use on a demo database: every advising student
changes the inputs of the next timetable."""
import argparse
import os
import random
import re
import sys
from collections import defaultdict
import httpx

FIRST = ['Omar', 'Mariam', 'Youssef', 'Nour', 'Ahmed', 'Salma', 'Karim', 'Laila', 'Hassan', 'Farida', 'Ali', 'Hana', 'Mostafa', 'Jana', 'Ziad', 'Malak']
LAST = ['Hamed', 'Saleh', 'Fathy', 'Mansour', 'Adel', 'Ezzat', 'Naguib', 'Ramadan', 'Shawky', 'Khalil', 'Sabry', 'Lotfy']


class Api:
    def __init__(self):
        self.c = httpx.Client(base_url=os.environ.get('JADWAI_URL', 'http://127.0.0.1:8011').rstrip('/') + '/api', headers={'X-Jadwai-Request': '1'}, timeout=120)
        self.c.post('/auth/login', json={'email': os.environ['JADWAI_EMAIL'], 'password': os.environ['JADWAI_PASSWORD']}).raise_for_status()

    def get(self, path):
        r = self.c.get(path); r.raise_for_status(); return r.json()

    def write(self, method, path, body=None):
        version = self.get('/workspace')['version']
        return self.c.request(method, path, json=body, headers={'If-Match': f'"{version}"'})


def plan(ws, count, rng):
    groups = {r['id']: r for r in ws['records'] if r['kind'] == 'groups'}
    activities = [r for r in ws['records'] if r['kind'] == 'courses' and r.get('course_id')]
    joinable = defaultdict(set)  # course -> groups that have sessions of it
    for a in activities:
        joinable[a['course_id']] |= set(a['group_ids'])
    home_courses = defaultdict(set)
    for course, gs in joinable.items():
        for g in gs:
            home_courses[g].add(course)
    by_year = defaultdict(set)
    for course, gs in joinable.items():
        for g in gs:
            by_year[groups[g].get('year')].add(course)
    major = lambda course: {groups[g].get('major') for g in joinable[course]}
    students, kinds = [], ['retake'] * 5 + ['section'] * 3 + ['elective'] * 2
    candidates = [g for g in groups if home_courses[g]]
    while len(students) < count and candidates:
        home = rng.choice(candidates); year = groups[home].get('year') or 1; kind = rng.choice(kinds)
        mine = sorted(home_courses[home])
        if kind == 'retake' and year > 1:
            # Failed a course from the year before: retake it with a group of that year.
            course = rng.choice(sorted(by_year[year - 1]))
            changes = [{'action': 'add', 'course_id': course, 'group_id': rng.choice(sorted(joinable[course])), 'why': 'retake'}]
            if len(mine) > 2 and rng.random() < 0.5:
                changes.append({'action': 'drop', 'course_id': rng.choice(mine), 'group_id': None, 'why': 'lighter load'})
        elif kind == 'section':
            # Same course, another group's sessions (a clash with work or another course).
            options = [c for c in mine if len(joinable[c]) > 1]
            if not options:
                continue
            course = rng.choice(options)
            changes = [{'action': 'drop', 'course_id': course, 'group_id': None, 'why': 'section change'},
                       {'action': 'add', 'course_id': course, 'group_id': rng.choice(sorted(joinable[course] - {home})), 'why': 'section change'}]
        else:
            # An elective from another programme of the same year instead of one of their own.
            others = [c for c in by_year[year] if c not in mine and not major(c) & {groups[home].get('major')}]
            if not others or len(mine) < 2:
                continue
            course = rng.choice(sorted(others))
            changes = [{'action': 'drop', 'course_id': rng.choice(mine), 'group_id': None, 'why': 'elective swap'},
                       {'action': 'add', 'course_id': course, 'group_id': rng.choice(sorted(joinable[course])), 'why': 'elective swap'}]
        n = len(students) + 1
        students.append({'code': f'DEMO-{n:04d}', 'name': f'{rng.choice(FIRST)} {rng.choice(LAST)}', 'group_id': home, 'changes': changes})
    return students


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=60)
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--clear', action='store_true', help='remove existing DEMO- advising students first')
    args = parser.parse_args()
    api = Api()
    if args.clear:
        for s in api.get('/advising-students')['students']:
            if s['code'].startswith('DEMO-'):
                api.write('DELETE', f"/advising-students/{s['id']}")
    ws = api.get('/workspace')
    added, reasons = 0, defaultdict(int)
    for student in plan(ws, args.count, random.Random(args.seed)):
        why = sorted({c.pop('why') for c in student['changes']})
        r = api.write('POST', '/advising-students', student)
        if r.status_code == 201:
            added += 1
            for w in why:
                reasons[w] += 1
        elif r.status_code != 409:
            print(f"Skipped {student['code']}: {r.status_code} {r.text[:120]}", file=sys.stderr)
    print(f"Added {added} advising students: " + ', '.join(f'{k} {v}' for k, v in sorted(reasons.items())))


if __name__ == '__main__':
    main()
