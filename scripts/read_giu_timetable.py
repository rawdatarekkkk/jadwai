"""Read a GIU weekly timetable workbook (one sheet per day: SAT … THURS) into a list of sessions.

The grid is written for people: column B names a cohort ("2nd BUSINESS ADMINISTRATION"), C/D a stream or
major, and E–I the five periods. A cell holds a course and usually a group ("Macroeconomics T3",
"CS II 5", "Physics lab 6 (S3.237)"); lectures usually carry a room instead of a group. Cells merged across
several periods are one session covering each of them. German/English language classes (DE, AS, SM, AE,
CPS, RPW) are not in the staff planning and are marked separately, as are "Day off" cells. Summary rows
("Rooms", "lecture halls", "CS labs", "Language labs") give the rooms counted per period.

    python scripts/read_giu_timetable.py WORKBOOK.xlsx  -> prints a summary; import read() for the sessions.
"""
import re
import sys
from collections import Counter

from openpyxl import load_workbook

DAYS = {'SAT': 'Saturday', 'SUN': 'Sunday', 'MON': 'Monday', 'TUES': 'Tuesday', 'WED': 'Wednesday', 'THURS': 'Thursday'}
SUMMARY = ('rooms', 'lecture halls', 'large lecture halls', 'cs labs', 'language labs')
LANGUAGE = re.compile(r'\b\d*\s*(?:DE|AS|SM|AE|CPS|RPW)\s*\d*\b(?!\w)')
ROOM = re.compile(r'\b(?:[A-Z]\d?\.\d{2,3}|[A-Z]\d-?\d{3}|TC\d{1,2}|[A-Z]{1,2}-\d{3}|S\d\.\d{3})\b', re.I)


def faculty_of(header, stream):
    h, s = f'{header} {stream}'.upper(), stream.upper()
    if 'BUSINESS ADMIN' in h: return 'BA'
    if 'INFORMATICS' in s and 'BUSINESS' in s or 'BUSINESS INFORMATICS' in h: return 'BI'
    if 'PHYSICAL' in h: return 'PT'
    if re.search(r'\bPHE\b', header.upper()): return 'PHARMA'  # its stream reads "Pharmaceutical Engineering"
    if re.search(r'\bBIO\b', header.upper()): return 'BIO'
    if 'ENGINEERING' in h: return 'ENG'
    if 'ARCHITECTURE' in h: return 'ARCH'
    if 'NFORMATICS' in h: return 'INF'
    if re.search(r'\bPHE\b', h): return 'PHARMA'
    if re.search(r'\bBIO\b', h): return 'BIO'
    if 'DESIGN' in h: return 'DESIGN'
    return None


def kind_of(text):
    t = text.lower()
    if re.search(r'\bday\s*off\b|^free$', t): return 'day_off'
    if LANGUAGE.search(text) and not re.search(r'[a-z]{4,}', re.sub(LANGUAGE, '', text), re.I): return 'language'
    return 'teaching'


def groups_of(text):
    """Group numbers named in a cell: 'T3' / 'P12' / 'lab 8/9' / 'Programming 4' -> [3] / [12] / [8, 9] / [4]."""
    t = ROOM.sub(' ', text)
    t = re.sub(r'\([^)]*\)', ' ', t)
    m = re.search(r'(?:\b[TP]\s?|\blab\s+|\s)(\d{1,2}(?:\s*/\s*\d{1,2})*)\s*$', t.strip(), re.I)
    return [int(x) for x in re.findall(r'\d+', m.group(1))] if m else []


def read(path):
    wb = load_workbook(path, data_only=True)
    sessions, summaries = [], []
    for sheet, day in DAYS.items():
        ws = wb[sheet]
        spans = {}
        for rng in ws.merged_cells.ranges:
            spans[(rng.min_row, rng.min_col)] = (rng.min_col, rng.max_col)
        header = stream = ''
        for r, row in enumerate(ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=10, values_only=True), 1):
            b, c, d = (str(x).strip() if x else '' for x in row[1:4])
            if b and 'SCHEDULE' not in b.upper():
                header, stream = b, ''
            if c:
                stream = c if c.lower() not in SUMMARY else stream
            if d:
                stream = f'{c or stream.split(" / ")[0]} / {d}'
            if c.upper().startswith('MAJORS') or re.match(r'\d{1,2}:\d{2}\s*-', str(row[4] or '')):
                continue  # the period header row
            if c.lower() in SUMMARY:
                summaries.append({'day': day, 'what': c.lower(), 'header': header, 'counts': [row[i] for i in range(4, 9)]})
                continue
            fac = faculty_of(header, stream)
            sem = re.match(r'\s*(\d)', header)
            for col in range(5, 10):
                v = row[col - 1]
                if v in (None, '') or not str(v).strip():
                    continue
                text = re.sub(r'\s+', ' ', str(v)).strip()
                first, last = spans.get((r, col), (col, col))
                for p in range(max(first, 5), min(last, 9) + 1):
                    sessions.append({'day': day, 'period': p - 5, 'faculty': fac, 'semester': int(sem.group(1)) if sem else None,
                                     'cohort': header, 'stream': stream, 'text': text, 'kind': kind_of(text),
                                     'groups': groups_of(text), 'room': (ROOM.search(text).group(0).upper() if ROOM.search(text) else None),
                                     'sheet_row': r})
    return sessions, summaries


if __name__ == '__main__':
    s, summ = read(sys.argv[1])
    print(len(s), 'cells;', Counter(x['kind'] for x in s))
    print('by faculty:', Counter(x['faculty'] for x in s if x['kind'] == 'teaching'))
    print('unmapped headers:', Counter(x['cohort'] for x in s if not x['faculty']).most_common(8))
    print('teaching by day:', Counter(x['day'] for x in s if x['kind'] == 'teaching'))
    print('teaching by period:', sorted(Counter(x['period'] for x in s if x['kind'] == 'teaching').items()))
    print('with group numbers:', sum(1 for x in s if x['kind'] == 'teaching' and x['groups']), 'with a room:', sum(1 for x in s if x['kind'] == 'teaching' and x['room']))
