"""Build an Excel data-entry template from the workspace's imported source timetable.

Pre-fills every room, section/stream/group and course the workbook implies; yellow cells
are for the administrator (capacities, staff, positions, days off, group sizes, who teaches
what). A Check column flags anything derived by guesswork. Reads the database only.

    cd backend && set -a && source ../.env && set +a
    .venv/bin/python ../scripts/make_data_template.py ../data-entry/JadwAI-data-template.xlsx
"""
import difflib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from openpyxl import Workbook  # noqa: E402
from openpyxl.comments import Comment  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402
from sqlalchemy import select  # noqa: E402
from app.models import CourseCatalog, Record, SessionLocal, SourceTimetable  # noqa: E402

DAYS = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
PROGRAMMES = [  # (pattern on the section text, programme, short code)
    (r'BUSINESS\s*-?\s*INFORMATICS', 'Business Informatics', 'BI'),
    (r'N?FORMATICS', 'Informatics and Computer Science', 'INF'),
    (r'BUSINESS ADMINISTRATION', 'Business Administration', 'BA'),
    (r'ENGINEERING', 'Engineering', 'ENG'),
    (r'\bBIO\b', 'Biotechnology', 'BIO'),
    (r'\bPHE\b', 'Pharmaceutical Engineering', 'PHE'),
    (r'ARCHITECTURE', 'Architecture', 'ARC'),
]
ROOM_CODE = r'\b(?:[A-Z]{1,2}\d?[.\-]\d{3}|TC\d{2}|A\.0\d\d)\b'
ELECTIVE = re.compile(r'\b\d*\s*(?:DE|AE|AS|CPS|SM|RPW)\s*\d*\b', re.I)
FILL = PatternFill('solid', start_color='FFF2CC')       # cells to fill in
EXAMPLE = Font(name='Arial', italic=True, color='808080')
HEAD = Font(name='Arial', bold=True)
BODY = Font(name='Arial')


def key(text):
    return re.sub(r'[^a-z0-9]', '', (text or '').lower())


def section_of(text, track):
    """('Informatics and Computer Science', 'INF', 3) from '3rd NFORMATICS'."""
    ordinal = re.match(r'\s*(1st|ist|3rd|5th|7th)\b', text or '', re.I)
    semester = {'1st': 1, 'ist': 1, '3rd': 3, '5th': 5, '7th': 7}[ordinal.group(1).lower()] if ordinal else None
    for pattern, programme, short in PROGRAMMES:
        if re.search(pattern, text or '', re.I):
            return programme, short, semester
    if 'physical therapy' in (track or '').lower():
        return 'Physical Therapy', 'PT', semester
    return None, None, semester


def stream_of(track, programme):
    """Stream label and its explicit group range, e.g. ('BI (I)', range(1, 10))."""
    rng = re.search(r'[(\[)]?\s*(\d+)\s*[-–]\s*(\d+)\s*[)\]]?', track or '')
    base = re.sub(r'[(\[)]?\s*\d+\s*[-–]\s*\d+.*$', '', track or '').strip(' )(') if rng else (track or '').strip()
    base = re.sub(r'\s*\((?:\d+|\d*\s*gp)\)\s*$', '', base, flags=re.I)  # "(18)", "(1gp)"
    if base.count('(') > base.count(')'):
        base += ')'
    base = re.sub(r'\s+', ' ', re.sub(r'(?<=[a-z])(?=I{1,3}\b)', ' ', base))
    if rng and int(rng.group(2)) - int(rng.group(1)) > 40:
        rng = None  # a malformed range such as "30-321"; fall back to the cells
    if key(base) in ('', key(programme)) or key(base) in ('biotechnology', 'pharmaceuticalengineering', 'physicaltherapy'):
        base = 'All'
    return base, (range(int(rng.group(1)), int(rng.group(2)) + 1) if rng else None)


def numeral_of(stream):
    match = re.search(r'\b(I{1,3}|IV|VI?)\)?\s*$', stream)
    return match.group(1) if match else ''


def course_name(label):
    text = re.sub(ROOM_CODE, ' ', label or '')
    text = re.sub(r'\b(biweekly|labs?|tut(?:orial)?s?|lectures?|lec|practical|pr)\b', ' ', text, flags=re.I)
    text = re.sub(r'\(?\s*G\.?\s*\d+\s*\)?|Dr\.?\s*\w+', ' ', text)
    text = re.sub(r'\s*\([^)]*$', '', text)          # unbalanced "(software", "( 12 ROBOTICS"
    text = re.sub(r'\s*\([^)]*\d[^)]*\)', '', text)  # "(4 MNF)", "( 23AUTO+23 AUTO)"
    text = re.sub(r'[\s\d\-/(),.+]+$', '', text).strip(' -/(),.+')
    text = re.sub(r'\s+', ' ', text)
    if text.isupper() or text.islower():
        text = text.title() if len(text) > 4 else text.upper()
    if ELECTIVE.fullmatch(text) or len(re.sub(r'[^A-Za-z]', '', text)) < 4 or ELECTIVE.match(text):
        return None
    return text


def build(db):
    source = db.scalar(select(SourceTimetable))
    if not source:
        sys.exit('No imported source timetable in this workspace.')
    entries = source.payload['entries']
    catalog = db.scalars(select(CourseCatalog)).all()
    by_catalog_name = {key(c.name): c for c in catalog}
    for c in catalog:
        for variant in (c.source_info or {}).get('name_variants') or []:
            by_catalog_name.setdefault(key(variant), c)
    rooms = sorted((r for r in db.scalars(select(Record).where(Record.kind == 'rooms'))), key=lambda r: r.code)

    streams = defaultdict(lambda: {'groups': set(), 'ranged': False, 'spellings': Counter()})
    numerals = {}
    courses = defaultdict(lambda: {'spellings': Counter(), 'types': Counter(), 'streams': set(), 'blocks': 0, 'catalog': None})
    for e in entries:
        programme, short, semester = section_of(e['section_as_printed'], e['track_as_printed'])
        if not programme or not semester:
            continue
        stream, explicit = stream_of(e['track_as_printed'], programme)
        if stream == '':
            continue
        # Merge spelling variants of one stream ("Elect.Power System"/"Systems").
        # Only spellings with the same Roman numeral ("Engineering II" vs "III") may merge.
        numeral = numeral_of(stream)
        known = [k for (p, _, sem, k) in streams if (p, sem) == (programme, semester) and numerals.get(k) == numeral]
        close = difflib.get_close_matches(key(stream), known, n=1, cutoff=0.85)
        numerals.setdefault(close[0] if close else key(stream), numeral)
        stream_key = close[0] if close else key(stream)
        s = streams[(programme, short, semester, stream_key)]
        s['spellings'][stream] += 1
        if explicit:
            s['groups'].update(explicit); s['ranged'] = True
        for g in e.get('group_number_candidates') or []:
            if str(g).isdigit() and int(g) <= 60:
                s['groups'].add(int(g))
        name = course_name(e['course_label_candidate'])
        if not name:
            continue
        matched = next((c for c in catalog if c.id == e.get('matched_course_id')), None) or by_catalog_name.get(key(name))
        if not matched:
            near = difflib.get_close_matches(key(name), list(by_catalog_name), n=1, cutoff=0.88)
            matched = by_catalog_name[near[0]] if near else None
        # Merge spelling variants within one programme-semester ("Pogrammimg III").
        pool = [k for (p, sem, k) in courses if (p, sem) == (programme, semester) and not k.startswith('code:')]
        close = difflib.get_close_matches(key(name), pool, n=1, cutoff=0.86)
        # One row per catalogue code within a programme semester.
        c = courses[(programme, semester, 'code:' + matched.code if matched else close[0] if close else key(name))]
        c['spellings'][matched.name if matched else name] += 1
        c['types'][e.get('activity_type_candidate') or 'unspecified'] += 1
        c['streams'].add(stream_key); c['blocks'] += 1
        c['catalog'] = c['catalog'] or matched
    # A label-less "All" stream next to named streams is stray cells, not a cohort.
    named = {(p, sem) for (p, _, sem, k) in streams if k != 'all'}
    for k in [k for k in streams if k[3] == 'all' and (k[0], k[2]) in named]:
        del streams[k]
    for (programme, semester, _), c in courses.items():
        c['streams'] = {k for k in c['streams'] if (programme, next(iter(sh for (p, sh, sem, kk) in streams if p == programme), ''), semester, k) in streams}
    return rooms, streams, courses


def sheet(wb, title, headers, widths, notes):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for i, cell in enumerate(ws[1]):
        cell.font = HEAD
        ws.column_dimensions[cell.column_letter].width = widths[i]
        if headers[i] in notes:
            cell.comment = Comment(notes[headers[i]], 'JadwAI')
    ws.freeze_panes = 'A2'
    return ws


def row(ws, values, fill_columns=(), example=False):
    ws.append(values)
    for i, cell in enumerate(ws[ws.max_row]):
        cell.font = EXAMPLE if example else BODY
        if i in fill_columns and not example:
            cell.fill = FILL


def main(target):
    with SessionLocal() as db:
        rooms, streams, courses = build(db)
    wb = Workbook()
    readme = wb.active; readme.title = 'Read me'
    lines = [
        'JadwAI data-entry template',
        'Built from the imported GIU-WINTER 26 timetable, the course catalogue and the 65 room codes already in JadwAI.',
        '',
        'How to fill it in',
        '1. Yellow cells are yours to fill. Everything else was derived from the workbook; correct it if it is wrong.',
        '2. Row 2 of each sheet is a grey EXAMPLE row showing the format. Leave it; the importer skips it.',
        '3. The Check column flags guesses (for example an activity type the timetable did not state). Clear it once checked.',
        '4. Delete a row to leave something out. Add rows for anything missing.',
        '5. Lists separate several values with | (for example lecture|exam_hall, or T-AH|T-MS).',
        '',
        'Sheets',
        'Rooms: capacity and uses (lecture, lab, flexible, exam_hall); features such as Data Science Lab or Workshop.',
        'Staff: every doctor and TA, with a short unique code you choose, their position and weekly day off.',
        'Groups: one row per tutorial/lab group with its number of students. Lectures are shared by all groups of a stream.',
        'Courses: one row per course and programme semester. Give lecture, tutorial and lab sessions per week and who may teach them:',
        '         Doctors (lectures) and TAs (tutorials and labs) as staff codes from the Staff sheet. Every TA must teach something.',
        '',
        'When done, save the file and send it back; the importer checks every row and reports problems before changing anything.',
    ]
    for line in lines:
        readme.append([line])
    readme['A1'].font = Font(name='Arial', bold=True, size=14)
    for r in readme.iter_rows(min_row=2):
        r[0].font = BODY
    readme['A4'].font = HEAD; readme['A11'].font = HEAD
    readme.column_dimensions['A'].width = 130
    readme['A20'] = 'Legend'; readme['A20'].font = HEAD
    readme['A21'] = 'Fill in'; readme['A21'].fill = FILL; readme['A21'].font = BODY
    readme['A22'] = 'Example row (skipped by the importer)'; readme['A22'].font = EXAMPLE

    lists = wb.create_sheet('Lists')
    lists.append(['Position', 'Day off', 'Activity type'])
    for i, values in enumerate([['doctor', 'ta'], DAYS, ['lecture', 'tutorial', 'lab']]):
        for j, value in enumerate(values):
            lists.cell(row=j + 2, column=i + 1, value=value)
    lists.sheet_state = 'hidden'

    ws = sheet(wb, 'Rooms', ['Code', 'Name', 'Capacity', 'Uses', 'Features', 'Check'], [12, 26, 11, 30, 34, 44],
               {'Uses': 'One or more of lecture, lab, flexible, exam_hall separated by |', 'Capacity': 'Seats for teaching'})
    row(ws, ['EXAMPLE', 'Lecture Hall A', 260, 'lecture|exam_hall', 'Projector', ''], example=True)
    for r in rooms:
        info = r.data
        row(ws, [r.code, r.name, info.get('capacity'), '|'.join(info.get('room_types') or []), '|'.join(info.get('equipment') or []),
                 '' if info.get('capacity') else 'Capacity and uses not in the workbook'], fill_columns=(2, 3, 4))

    ws = sheet(wb, 'Staff', ['Code', 'Name', 'Department', 'Position', 'Day off', 'Check'], [12, 30, 34, 12, 14, 40],
               {'Code': 'Short unique code, used in the Courses sheet', 'Position': 'doctor teaches lectures; ta teaches tutorials and labs'})
    row(ws, ['T-MA', 'Mona Adel', 'Informatics and Computer Science', 'ta', 'Saturday', ''], example=True)
    for _ in range(150):
        row(ws, [None] * 6, fill_columns=(0, 1, 2, 3, 4))
    for col, source in (('D', '=Lists!$A$2:$A$3'), ('E', '=Lists!$B$2:$B$8')):
        dv = DataValidation(type='list', formula1=source, allow_blank=True); ws.add_data_validation(dv); dv.add(f'{col}3:{col}400')

    ws = sheet(wb, 'Groups', ['Code', 'Programme', 'Semester', 'Year', 'Stream', 'Group', 'Students', 'Check'], [24, 32, 10, 7, 40, 8, 10, 46],
               {'Students': 'Number of students in this tutorial/lab group', 'Stream': 'Groups of one stream share lectures'})
    row(ws, ['INF3-ACS-I-G01', 'Informatics and Computer Science', 3, 2, 'Applied Computer science & Informatics I', 1, 28, ''], example=True)
    stream_names = {}
    for (programme, short, semester, skey), s in sorted(streams.items(), key=lambda x: (x[0][0], x[0][2], x[0][3])):
        name = s['spellings'].most_common(1)[0][0]
        stream_names[(programme, semester, skey)] = name
        tag = re.sub(r'[^A-Z0-9]', '', ''.join(w[0] for w in re.findall(r'[A-Za-z]+', name)).upper())[:5] or 'ALL'
        tag += ''.join(re.findall(r'\b(I{1,3}|IV|V|VI)\b', name))
        note = '' if s['ranged'] else 'Group numbers read from cell text; check them'
        if len(s['groups']) > 25 and not s['ranged']:
            note = 'Many group numbers found; likely includes noise. Check.'
        for g in sorted(s['groups']) or [1]:
            row(ws, [f'{short}{semester}-{tag}-G{g:02d}', programme, semester, (semester + 1) // 2, name, g, None, note], fill_columns=(6,))

    ws = sheet(wb, 'Courses', ['Code', 'Name', 'Programme', 'Semester', 'Streams', 'Lectures/week', 'Tutorials/week', 'Labs/week', 'Minutes',
                               'Doctors', 'TAs', 'Room features', 'Expected students', 'Workbook blocks', 'Check'],
               [12, 38, 30, 9, 50, 12, 13, 10, 9, 22, 30, 22, 12, 12, 48],
               {'Streams': 'Streams (from the Groups sheet) taking this course, separated by |',
                'Lectures/week': 'Lecture sessions per week, shared by each stream', 'Tutorials/week': 'Per group', 'Labs/week': 'Per group',
                'Doctors': 'Staff codes of doctors who may give the lectures (|)', 'TAs': 'Staff codes of TAs who may give tutorials/labs (|)',
                'Room features': 'Features a lab room must have, e.g. Data Science Lab'})
    row(ws, ['ICS504', 'Machine Learning', 'Informatics and Computer Science', 5, 'Data Science', 1, 0, 1, 90, 'D-SA', 'T-MA|T-NS', 'Data Science Lab', '', 12, ''], example=True)
    for (programme, semester, ckey), c in sorted(courses.items(), key=lambda x: (x[0][0], x[0][1], -x[1]['blocks'])):
        if c['blocks'] < 2 and not c['catalog']:
            continue  # single stray cells are usually notes, not courses
        name = c['spellings'].most_common(1)[0][0]
        types = c['types']
        labs, tuts = int(types['lab'] > 0), int(types['tutorial'] > 0)
        checks = []
        if not labs and not tuts:
            tuts = 1; checks.append('Activity type not stated in the timetable; tutorial assumed')
        if not c['catalog']:
            checks.append('No course code found; add one')
        siblings = [x['spellings'].most_common(1)[0][0] for (p, sem, k), x in courses.items() if (p, sem) == (programme, semester) and k != ckey]
        similar = [x for x in siblings if difflib.SequenceMatcher(None, key(x), key(name)).ratio() > 0.7 or key(x).startswith(key(name)) or key(name).startswith(key(x))]
        if similar:
            checks.append('Possibly the same course as: ' + ', '.join(similar[:2]))
        streams_text = '|'.join(sorted(stream_names.get((programme, semester, s), s) for s in c['streams']))
        row(ws, [c['catalog'].code if c['catalog'] else None, name, programme, semester, streams_text, 1, tuts, labs, 90,
                 None, None, None, c['catalog'].expected_students if c['catalog'] else None, c['blocks'], '; '.join(checks)],
            fill_columns=(0, 9, 10) if not c['catalog'] else (9, 10))
    wb.move_sheet('Lists', offset=len(wb.sheetnames))
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    wb.save(target)
    print(f'{target}: {len(rooms)} rooms, {sum(len(s["groups"]) or 1 for s in streams.values())} groups, '
          f'{wb["Courses"].max_row - 2} courses')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data-entry/JadwAI-data-template.xlsx')
