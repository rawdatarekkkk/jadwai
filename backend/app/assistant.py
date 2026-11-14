"""JAI chat: answer questions about the timetable and prepare website actions.

Understanding runs in two steps, both on this server:
1. Built-in patterns (English, Arabic, Egyptian Arabic) recognise the common questions and
   commands instantly: room / instructor / group availability and timetables, free rooms,
   when a course meets, generating a timetable for a programme or year, exam timetables,
   PDFs and the state of the latest run.
2. When those don't recognise the message, the locally hosted model (Ollama) is asked to
   map it onto the same small set of intents. The model never acts by itself and never
   sees more than the names the message mentions: its answer goes through the same
   resolution and handlers as the built-in path.

Questions are answered here. Commands come back as a proposed action that the admin
confirms; the browser then calls the website's own endpoints (the same ones the pages
use), so every check, lock and validation still applies. Nothing is published.
"""
import json
import os
import re
from datetime import date
import httpx
from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select
from app.dependencies import administrator, db_session
from app.models import CourseCatalog, ExamRun, Record, ScheduleRun, Workspace
from app.rule_parser import ARABIC_DIGITS, DAYS, TIME, days_in, find_records, hour, mentions, normalise, plain, times
from app.schemas import Strict
from app.assistant_records import KIND_WORDS, converse, fill, first_fill, record_kind

router = APIRouter(prefix='/api/assistant')
ARABIC = re.compile(r'[؀-ۿ]')
INTENTS = ('room_schedule', 'free_rooms', 'instructor_schedule', 'group_schedule', 'course_schedule',
           'generate_timetable', 'exam_timetable', 'download_pdf', 'status', 'help', 'create_record')
CANCEL_WORDS = ('cancel', 'never mind', 'nevermind', 'forget it', 'stop', 'الغاء', 'إلغاء', 'خلاص', 'سيبك', 'انسى')


class Ask(Strict):
    text: str = Field(min_length=1, max_length=2000)
    previous: dict | None = None  # the last understood message, for follow-ups ("and on Monday?")
    use_model: bool = False       # ask the local model when the built-in patterns don't recognise it


# ----------------------------------------------------------------------------- the data
def latest_run(db):
    """The published teaching timetable, otherwise the newest completed one that passed validation."""
    published = db.scalar(select(ScheduleRun).where(ScheduleRun.published_at.isnot(None)))
    if published and published.status == 'completed':
        return published
    for row in db.scalars(select(ScheduleRun).where(ScheduleRun.status == 'completed').order_by(ScheduleRun.created_at.desc()).limit(20)):
        if (row.result or {}).get('validation', {}).get('passed'):
            return row
    return None


def view_of(db):
    """Everything an answer needs, read once so the DB lock can be released before a model call."""
    ws = db.get(Workspace, 1)
    records = [{'id': r.id, 'kind': r.kind, 'data': r.data} for r in db.scalars(select(Record).order_by(Record.id))]
    run = latest_run(db)
    sessions = []
    if run:
        # The run's own snapshot names the records it scheduled (they may have changed since).
        snap = {r['id']: r for r in run.snapshot['records']}
        for a in run.result['assignments']:
            act = snap.get(a['activity_id'], {})
            sessions.append({**a, 'course': act.get('name', '?'), 'code': act.get('code', ''), 'type': act.get('activity_type', ''),
                             'groups': act.get('group_ids', []), 'room': snap.get(a.get('room_id'), {}).get('code', ''),
                             'instructor': snap.get(a.get('instructor_id'), {}).get('name', '')})
    exams = db.scalar(select(ExamRun).order_by(ExamRun.created_at.desc()).limit(1))
    return {'calendar': {'days': ws.days, 'start_hour': ws.start_hour, 'end_hour': ws.end_hour,
                         'period_minutes': ws.period_minutes, 'teaching_periods': ws.teaching_periods or []},
            'records': records, 'version': ws.version, 'sessions': sessions,
            'second_chance': [c.id for c in db.scalars(select(CourseCatalog)) if c.second_chance],
            'run': {'id': run.id, 'name': run.name, 'published': bool(run.published_at), 'stale': run.input_version != ws.version,
                    'created_at': run.created_at.isoformat(), 'sessions': len(run.result['assignments'])} if run else None,
            'exam_run': {'id': exams.id, 'status': (exams.result or {}).get('status'), 'kind': (exams.snapshot.get('settings') or {}).get('kind')} if exams else None,
            'last_status': last_status(db)}


def last_status(db):
    row = db.scalar(select(ScheduleRun).order_by(ScheduleRun.created_at.desc()).limit(1))
    if not row:
        return None
    return {'id': row.id, 'status': row.status, 'passed': (row.result or {}).get('validation', {}).get('passed'),
            'sessions': len((row.result or {}).get('assignments') or []), 'scope': (row.snapshot or {}).get('plan', {}).get('scope')}


# ----------------------------------------------------------------------------- understanding
def clock(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def programmes(records):
    return sorted({(r['data'].get('major') or '') for r in records if r['kind'] == 'groups'} - {''})


def initials(name):
    return ''.join(w[0] for w in re.findall(r'[A-Za-z]+', name) if w.lower() not in ('and', 'of')).lower()


COMMON = {'is', 'it', 'in', 'on', 'at', 'as', 'an', 'or', 'to', 'do', 'be', 'by', 'if', 'me', 'my', 'no', 'of', 'so', 'up', 'we', 'am', 'pm'}


def find_programme(text, records):
    """Programmes the text names in full or by initials ("BA" for Business Administration)."""
    found = []
    for p in programmes(records):
        short = initials(p)
        if mentions(text, normalise(p)) or (len(short) >= 2 and short not in COMMON and re.search(rf'(?<![\w]){short}(?=\s|\d|-|$|[^\w])', text)):
            found.append(p)
    return found


YEAR_WORDS = {'first': 1, '1st': 1, 'second': 2, '2nd': 2, 'third': 3, '3rd': 3, 'fourth': 4, '4th': 4, 'fifth': 5, '5th': 5,
              'اولى': 1, 'الاولى': 1, 'اول': 1, 'تانية': 2, 'ثانية': 2, 'الثانية': 2, 'تانيه': 2, 'تالتة': 3, 'ثالثة': 3, 'الثالثة': 3,
              'تالته': 3, 'رابعة': 4, 'الرابعة': 4, 'رابعه': 4, 'خامسة': 5, 'الخامسة': 5}


def find_year(text):
    m = re.search(r'(?:year|yr|y|سنة|سنه|الفرقة|فرقة)\s*-?\s*(\d)\b', text) or re.search(r'(?<![\w])[a-z]{2,5}\s?(\d)(?=[\s-]*g\d)', text)
    if m:
        return int(m.group(1))
    for word, n in YEAR_WORDS.items():
        if re.search(rf'(?<![\w]){word}(?:\s+(?:year|yr))?(?![\w])', text) and (word.isascii() is False or 'year' in text):
            return n
    return None


def find_group(text, records, programme, year):
    """A student group by code ("INF1-G7"), or by programme + year + group number ("BA Y3 G7")."""
    groups = [r for r in records if r['kind'] == 'groups']
    for g in groups:
        if mentions(text, normalise(g['data'].get('code', ''))) or mentions(text, normalise(g['data'].get('name', ''))):
            return [g]
    number = re.search(r'(?<![\w])(?:g|group|جروب|مجموعة|مجموعه)\s*-?\s*(\d{1,2})(?!\d)', text)
    if not number:
        return []
    tag = f"g{number.group(1)}"
    return [g for g in groups if re.search(rf'(?<![\w]){tag}$', normalise(g['data'].get('code', '')) + '') or normalise(g['data'].get('name', '')).endswith(' ' + tag)
            if (not programme or g['data'].get('major') in programme) and (not year or g['data'].get('year') == year)] if (programme or year) else []


def at_time(text):
    m = re.search(r'(?:at|@|الساعة|الساعه|ساعة)\s*' + TIME, text)
    return round(hour(m.groups()) * 60) if m else None


def window(text, calendar):
    """(start, end) minutes the message asks about, a single moment, or None for the whole day."""
    moment = at_time(text)
    if moment is not None:
        return moment, moment + 1
    span = times(text, calendar)
    if span:
        return round(span[0] * 60), round(span[1] * 60)
    # A bare clock time ("Monday 11:30", "2pm") is a moment too.
    bare = re.search(r'(?<![\d-])(\d{1,2}):(\d{2})(?!\d)|(?<![\d-])(\d{1,2})\s*(am|pm)\b', text)
    if bare:
        h, m, h2, suffix = bare.groups()
        moment = round(hour((h or h2, m, suffix)) * 60)
        return moment, moment + 1
    return None


MONTHS = {m: i for i, m in enumerate(('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'), 1)}
MONTHS.update({'يناير': 1, 'فبراير': 2, 'مارس': 3, 'ابريل': 4, 'مايو': 5, 'يونيو': 6, 'يوليو': 7, 'اغسطس': 8, 'سبتمبر': 9, 'اكتوبر': 10, 'نوفمبر': 11, 'ديسمبر': 12})


def find_dates(text, today=None):
    """An exam period: '2026-12-20 to 2026-12-31', '20-31 Dec', '20 Dec - 3 Jan', 'from Dec 20 to Dec 31'."""
    today = today or date.today()
    iso = re.findall(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
    if len(iso) >= 2:
        return date(*map(int, iso[0])), date(*map(int, iso[1]))
    month = r'(' + '|'.join(sorted(MONTHS, key=len, reverse=True)) + r')[a-z]*'
    pairs = re.findall(r'(\d{1,2})\s*' + month + r'|' + month + r'\s*(\d{1,2})', text)
    days = [(int(a or d), MONTHS[b or c]) for a, b, c, d in pairs]
    if len(days) < 2:
        m = re.search(r'(\d{1,2})\s*(?:-|–|to|الى|إلى|لحد)\s*(\d{1,2})\s*' + month, text)
        if m:
            days = [(int(m.group(1)), MONTHS[m.group(3)]), (int(m.group(2)), MONTHS[m.group(3)])]
    if len(days) < 2:
        return None
    (d1, m1), (d2, m2) = days[:2]
    year = re.search(r'\b(20\d\d)\b', text)
    y1 = int(year.group(1)) if year else (today.year if (m1, d1) >= (today.month, today.day) else today.year + 1)
    start = date(y1, m1, d1)
    end = date(y1 + (m2 < m1), m2, d2)
    return (start, end) if end >= start else None


ASK_WORDS = ('free', 'available', 'availab', 'busy', 'empty', 'vacant', 'occupied', 'booked', 'فاضي', 'فاضية', 'فاضيه', 'متاح', 'متاحة', 'مشغول', 'مشغولة', 'فارغ', 'فارغة')
SCHEDULE_WORDS = ('schedule', 'timetable', 'what does', 'what is in', "what's in", 'who is in', 'classes', 'sessions', 'teach', 'lectures',
                  'جدول', 'محاضرات', 'سكشن', 'بيدرس', 'عنده', 'عندها', 'عندهم')
CREATE_WORDS = ('generate', 'create', 'make', 'build', 'produce', 'schedule for', 'prepare', 'run the solver', 'اعمل', 'اعمللي', 'إعمل', 'انشئ', 'أنشئ', 'ولد', 'جهز', 'كون', 'اعملي')
EXAM_WORDS = {'final': ('final', 'finals', 'نهائي', 'النهائي', 'فاينل'), 'midterm': ('midterm', 'midterms', 'mid-term', 'ميدترم', 'منتصف'),
              'quiz': ('quiz', 'quizzes', 'كويز', 'اختبار قصير', 'اختبارات قصيرة')}
PDF_WORDS = ('pdf', 'download', 'print', 'export', 'نزل', 'تحميل', 'اطبع', 'طباعة')
STATUS_WORDS = ('status', 'last run', 'latest run', 'is the timetable valid', 'progress', 'how many sessions', 'summary', 'حالة', 'ملخص', 'آخر جدول', 'اخر جدول')
ALL_WORDS = ('all of', 'all groups', 'all the groups', 'whole', 'every group', 'all years', 'all programmes', 'all programs', 'everyone', 'all of them',
             'كلها', 'كلهم', 'الكل', 'كل المجموعات', 'كل الجروبات', 'السنة كلها', 'كل السنين')
HELP_WORDS = ('help', 'what can you do', 'how do i', 'مساعدة', 'تقدر تعمل ايه', 'بتعمل ايه')
ROOM_HINT = ('room', 'hall', 'lab', 'قاعة', 'قاعه', 'معمل', 'مدرج')


def has(text, words):
    return any(w in text for w in words)


def understand(raw, view, previous=None):
    """Built-in understanding: {'intent', 'slots', 'missing', 'ambiguous'} or intent 'unknown'."""
    text = normalise(raw).translate(ARABIC_DIGITS)
    records, calendar = view['records'], view['calendar']
    rooms, rambig = find_records(text, records, 'rooms')
    instructors, iambig = find_records(text, records, 'instructors')
    courses, cambig = find_records(text, records, 'courses')
    progs = find_programme(text, records)
    year = find_year(text)
    groups = find_group(text, records, progs, year)
    days = [d for d in days_in(text, calendar) if d]
    span = window(text, calendar)
    exam = next((k for k, words in EXAM_WORDS.items() if has(text, words)), None)
    slots = {'rooms': [r['id'] for r in rooms], 'instructors': [r['id'] for r in instructors], 'courses': [r['id'] for r in courses],
             'groups': [g['id'] for g in groups], 'programmes': progs, 'year': year, 'days': days, 'window': span}
    ambiguous = [*rambig, *iambig]
    intent = None
    asked = previous and previous.get('intent') in INTENTS and previous.get('asking')
    if asked and re.fullmatch(r'(?:' + '|'.join(CANCEL_WORDS) + r')[.!]?', text):
        return {'intent': 'cancel', 'slots': {}, 'ambiguous': []}
    new_record = record_kind(text)
    if asked and previous['intent'] == 'create_record' and new_record is None:
        # Inside a create conversation every reply answers the question JAI asked.
        old = dict(previous.get('slots') or {})
        form, field = dict(old.get('form') or {}), old.get('field')
        old.pop('unreadable', None)
        if field == 'kind':
            kind = next((k for k, words in KIND_WORDS.items() if any(w in f' {text} ' or w.strip() == text for w in words)), None)
            return {'intent': 'create_record', 'slots': {**old, 'kind': kind, 'form': first_fill(kind, raw, text, view) if kind else {}, **({} if kind else {'unreadable': True})}, 'ambiguous': []}
        value = fill(field, raw, text, view, form) if field else None
        if value is None:
            return {'intent': 'create_record', 'slots': {**old, 'unreadable': True}, 'ambiguous': []}
        form[field] = value
        return {'intent': 'create_record', 'slots': {**old, 'form': form}, 'ambiguous': []}
    if new_record is not None:
        if new_record == '':
            return {'intent': 'create_record', 'slots': {'kind': None}, 'ambiguous': []}
        return {'intent': 'create_record', 'slots': {'kind': new_record, 'form': first_fill(new_record, raw, text, view)}, 'ambiguous': []}
    # A short reply without a request of its own answers JAI's last question.
    answering = bool(previous and previous.get('intent') in INTENTS and previous.get('asking') and len(text.split()) <= 8
                     and not has(text, CREATE_WORDS + ASK_WORDS + SCHEDULE_WORDS + PDF_WORDS + STATUS_WORDS + HELP_WORDS)
                     and not any(has(text, w) for w in EXAM_WORDS.values()))
    if answering:
        # The answer to JAI's question ("BA5-G7", "all of them", "year 3", "20 Dec to 31 Dec") completes the previous request.
        old, new = previous.get('slots') or {}, {k: v for k, v in slots.items() if v}
        if not new.get('groups'):
            # "group 7" / "G7" typed on its own: a group of the programme and year being discussed.
            within = find_group(text, records, new.get('programmes') or old.get('programmes') or [], new.get('year') or old.get('year'))
            if within:
                new['groups'] = [g['id'] for g in within]
        if has(text, ('university', 'everything', 'الجامعة')):
            new['everything'] = True
        if has(text, ALL_WORDS) or re.search(r'(?<![\w])all(?![\w])', text):
            new['all_groups'] = True
            if old.get('programmes') and old.get('year') is None and not new.get('year'):
                new['all_years'] = True
            if not old.get('programmes') and not new.get('programmes'):
                new['all_programmes'] = True
        if previous['intent'] == 'exam_timetable' and (dates := find_dates(text)):
            new['dates'] = [d.isoformat() for d in dates]
        return {'intent': previous['intent'], 'slots': {**old, **new}, 'ambiguous': ambiguous, 'follow_up': True}
    elif has(text, HELP_WORDS) and len(text) < 40:
        intent = 'help'
    elif exam and (has(text, CREATE_WORDS) or 'timetable' in text or 'schedule' in text or 'جدول' in text):
        intent = 'exam_timetable'
        slots.update(exam_kind=exam, dates=[d.isoformat() for d in find_dates(text) or ()],
                     quiz_number=int(m.group(1)) if (m := re.search(r'(?:quiz|كويز)\s*(\d+)', text)) else None,
                     quiz_minutes=int(m.group(1)) if (m := re.search(r'(\d{2})\s*(?:min|minutes|دقيقة|دقيقه)', text)) else None)
    elif has(text, PDF_WORDS) and not has(text, ('add ', 'create ')):
        intent = 'download_pdf'
    elif has(text, CREATE_WORDS) and (has(text, ('timetable', 'schedule', 'جدول')) or progs or year):
        intent = 'generate_timetable'
        slots['everything'] = has(text, ('whole', 'all ', 'everything', 'entire', 'university', 'كل', 'الجامعة', 'كامل'))
    elif has(text, STATUS_WORDS):
        intent = 'status'
    elif has(text, ASK_WORDS) and not (rooms or instructors or groups) and has(text, ROOM_HINT + ('rooms', 'قاعات', 'معامل')):
        intent = 'free_rooms'
        slots['lab'] = has(text, ('lab', 'معمل', 'معامل'))
        slots['seats'] = int(m.group(1)) if (m := re.search(r'(\d{2,3})\s*(?:students|seats|people|طالب|مقعد)', text)) else None
    elif rooms:
        intent = 'room_schedule'
    elif instructors or (iambig and has(text, ('dr', 'doctor', 'prof', 'دكتور', 'د.', 'معيد') + SCHEDULE_WORDS + ASK_WORDS)):
        intent = 'instructor_schedule'
    elif groups or (progs and year):
        intent = 'group_schedule'
    elif courses:
        intent = 'course_schedule'
    elif previous and previous.get('intent') in INTENTS and (days or span):
        # A follow-up such as "and on Monday?" keeps the previous subject.
        old = previous.get('slots') or {}
        return {'intent': previous['intent'], 'slots': {**old, 'days': days or old.get('days', []), 'window': span or old.get('window')},
                'ambiguous': [], 'follow_up': True}
    return {'intent': intent or 'unknown', 'slots': slots, 'ambiguous': ambiguous}


# ----------------------------------------------------------------------------- answers
def say(ar, en_text, ar_text):
    return ar_text if ar else en_text


def overlaps(s, day, span):
    return s['day'] == day and (span is None or (s['start_minute'] < span[1] and span[0] < s['end_minute']))


def describe(s, ar, show=('course', 'room', 'instructor')):
    parts = [f"{s['day'] if not ar else AR_DAYS.get(s['day'], s['day'])} {clock(s['start_minute'])}–{clock(s['end_minute'])}"]
    if 'course' in show:
        parts.append(f"{s['course']} ({s['type']})" if s['type'] else s['course'])
    if 'room' in show and s['room']:
        parts.append(say(ar, 'room ', 'قاعة ') + s['room'])
    if 'instructor' in show and s['instructor']:
        parts.append(s['instructor'])
    return ' · '.join(parts)


AR_DAYS = {'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الاثنين', 'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء', 'Thursday': 'الخميس', 'Friday': 'الجمعة'}


def free_windows(busy, calendar):
    """Free teaching periods (or hours) of a day, given its busy sessions."""
    periods = calendar.get('teaching_periods') or [{'start': m, 'end': m + calendar['period_minutes']}
                                                    for m in range(calendar['start_hour'] * 60, calendar['end_hour'] * 60, calendar['period_minutes'])]
    return [p for p in periods if not any(s['start_minute'] < p['end'] and p['start'] < s['end_minute'] for s in busy)]


def by_id(view):
    return {r['id']: r for r in view['records']}


def subject_sessions(view, kind, ident):
    if kind == 'rooms':
        return [s for s in view['sessions'] if s.get('room_id') == ident]
    if kind == 'instructors':
        return [s for s in view['sessions'] if s.get('instructor_id') == ident]
    if kind == 'groups':
        return [s for s in view['sessions'] if ident in s['groups']]
    return [s for s in view['sessions'] if s['activity_id'] == ident]


def availability(view, kind, ident, slots, ar):
    """The answer for one room, instructor, group or course: free/busy at a time, or its day/week."""
    name = by_id(view)[ident]['data']
    label = name.get('code') if kind in ('rooms', 'groups') else name.get('name')
    mine = sorted(subject_sessions(view, kind, ident), key=lambda s: (view['calendar']['days'].index(s['day']) if s['day'] in view['calendar']['days'] else 9, s['start_minute']))
    days, span = slots.get('days') or [], slots.get('window')
    show = {'rooms': ('course', 'instructor'), 'instructors': ('course', 'room'), 'groups': ('course', 'room', 'instructor'), 'courses': ('room', 'instructor')}[kind]
    lines = []
    if days and span:
        for day in days:
            hits = [s for s in mine if overlaps(s, day, span)]
            when = f"{say(ar, day, AR_DAYS.get(day, day))} {clock(span[0])}" + (f"–{clock(span[1])}" if span[1] - span[0] > 1 else '')
            if hits:
                lines.append(say(ar, f'No: {label} is busy on {when}:', f'لا: {label} مشغول يوم {when}:'))
                lines += ['• ' + describe(s, ar, show) for s in hits]
            else:
                lines.append(say(ar, f'Yes: {label} is free on {when}.', f'نعم: {label} متاح يوم {when}.'))
        return lines
    for day in days or [None]:
        todays = [s for s in mine if day is None or s['day'] == day]
        head = say(ar, f"{label} on {day}:" if day else f"{label}'s week ({len(todays)} sessions):",
                   f"{label} يوم {AR_DAYS.get(day, day)}:" if day else f"أسبوع {label} ({len(todays)} محاضرة):")
        lines.append(head)
        lines += ['• ' + describe(s, ar, show) for s in todays[:40]] or [say(ar, '• Nothing scheduled.', '• لا يوجد شيء.')]
        if len(todays) > 40:
            lines.append(say(ar, f'… and {len(todays) - 40} more.', f'… و{len(todays) - 40} أخرى.'))
        if day and kind != 'courses':
            free = free_windows(todays, view['calendar'])
            lines.append(say(ar, 'Free: ', 'متاح: ') + (', '.join(f"{clock(p['start'])}–{clock(p['end'])}" for p in free) or say(ar, 'no free period', 'لا توجد فترة متاحة')))
    return lines


def free_rooms(view, slots, ar):
    days, span = slots.get('days') or [], slots.get('window')
    if not days or not span:
        return None, say(ar, 'Which day and time? For example: "free labs on Sunday at 10:00".', 'أي يوم وأي ساعة؟ مثلاً: "معامل فاضية يوم الأحد الساعة 10".')
    rooms = [r for r in view['records'] if r['kind'] == 'rooms']
    if slots.get('lab'):
        rooms = [r for r in rooms if 'lab' in (r['data'].get('room_types') or [r['data'].get('room_type')])]
    if slots.get('seats'):
        rooms = [r for r in rooms if (r['data'].get('capacity') or 0) >= slots['seats']]
    lines = []
    for day in days:
        busy = {s.get('room_id') for s in view['sessions'] if overlaps(s, day, span)}
        free = sorted((r for r in rooms if r['id'] not in busy), key=lambda r: (r['data'].get('capacity') or 0, r['data'].get('code', '')))
        when = f"{say(ar, day, AR_DAYS.get(day, day))} {clock(span[0])}" + (f"–{clock(span[1])}" if span[1] - span[0] > 1 else '')
        lines.append(say(ar, f'{len(free)} free rooms on {when}:', f'{len(free)} قاعة متاحة يوم {when}:'))
        lines += [f"• {r['data'].get('code')} · {r['data'].get('capacity') or '?'} {say(ar, 'seats', 'مقعد')}"
                  + (f" · {say(ar, 'reserved for ', 'محجوزة لـ ')}{', '.join(r['data'].get('reserved_majors'))}" if r['data'].get('reserved_majors') else '')
                  for r in free[:30]]
        if len(free) > 30:
            lines.append(say(ar, f'… and {len(free) - 30} more.', f'… و{len(free) - 30} أخرى.'))
    return lines, None


def scope_of(slots, records):
    progs, year = slots.get('programmes') or [], slots.get('year')
    if slots.get('groups'):
        # Just these groups: only their courses are placed (shared lectures come with their other groups).
        named = by_id({'records': records})
        return [{'programme': named[g]['data']['major'], 'year': named[g]['data'].get('year'), 'group': g} for g in slots['groups'][:10]]
    if not progs and year:
        progs = programmes(records)
    return [{'programme': p, 'year': year} for p in progs]


def generation_question(slots, view, ar):
    """A question when a timetable request leaves out who it is for, with the possible answers."""
    if slots.get('everything') or slots.get('groups'):
        return None
    groups = [r for r in view['records'] if r['kind'] == 'groups']
    progs, year = slots.get('programmes') or [], slots.get('year')
    if not progs and not year and not slots.get('all_programmes'):
        return {'text': [say(ar, 'Sure. Which programme is it for, or the whole university?', 'تمام. لأي برنامج، ولا للجامعة كلها؟')],
                'choices': [{'label': p, 'text': p} for p in programmes(view['records'])][:10] + [{'label': say(ar, 'Whole university', 'الجامعة كلها'), 'text': 'whole university'}],
                'asking': True}
    if len(progs) == 1 and not year and not slots.get('all_years'):
        years = sorted({g['data'].get('year') for g in groups if g['data'].get('major') == progs[0] and g['data'].get('year')})
        if len(years) > 1:
            return {'text': [say(ar, f'Which year of {progs[0]}?', f'أي سنة في {progs[0]}؟')],
                    'choices': [{'label': say(ar, f'Year {y}', f'سنة {y}'), 'text': f'year {y}'} for y in years] + [{'label': say(ar, 'All years', 'كل السنين'), 'text': 'all years'}],
                    'asking': True}
    if len(progs) == 1 and year and not slots.get('all_groups'):
        mine = sorted((g for g in groups if g['data'].get('major') == progs[0] and g['data'].get('year') == year),
                      key=lambda g: (len(g['data'].get('code', '')), g['data'].get('code', '')))
        if len(mine) > 1:
            return {'text': [say(ar, f'All {len(mine)} groups of {progs[0]} year {year}, or one group?', f'كل الـ{len(mine)} مجموعات في {progs[0]} سنة {year}، ولا مجموعة واحدة؟')],
                    'choices': [{'label': say(ar, f'All of year {year}', f'كل سنة {year}'), 'text': 'all of them'}] + [{'label': g['data']['code'], 'text': g['data']['code']} for g in mine[:15]],
                    'asking': True}
    return None


def answer(meaning, view, ar):
    """{'text': [...lines], 'action': {...} | None, 'needs': str | None}."""
    intent, slots = meaning['intent'], meaning['slots']
    run = view['run']
    if intent == 'cancel':
        return {'text': [say(ar, 'OK, cancelled. What else can I do?', 'تمام، تم الإلغاء. أقدر أساعد في إيه تاني؟')], 'forget': True}
    if intent == 'create_record':
        if not slots.get('kind'):
            slots['field'] = 'kind'
            slots['ar'] = ar
            sorry = [say(ar, "Sorry, I didn't catch that.", 'عذراً، لم أفهم.')] if slots.pop('unreadable', None) else []
            return {'text': sorry + [say(ar, 'What would you like to add?', 'تحب تضيف إيه؟')], 'asking': True,
                    'choices': [{'label': say(ar, 'An instructor', 'محاضر'), 'text': 'instructor'}, {'label': say(ar, 'A room', 'قاعة'), 'text': 'room'},
                                {'label': say(ar, 'A student group', 'مجموعة طلاب'), 'text': 'group'}, {'label': say(ar, 'A course', 'مقرر'), 'text': 'course'}]}
        ar = slots.setdefault('ar', ar)  # keep the language the conversation started in
        step = converse(slots, view, lambda en, a: a if ar else en)
        if 'form' in step:
            slots['form'] = step['form']
        slots['field'] = step.get('field')
        slots.pop('unreadable', None)
        return step
    if meaning.get('ambiguous') and intent in ('room_schedule', 'instructor_schedule', 'unknown'):
        kind = 'rooms' if intent == 'room_schedule' else 'instructors'
        options = [r['data']['name'] for r in view['records'] if r['kind'] == kind
                   and any(mentions(plain(r['data'].get('name', '')), part) for part in meaning['ambiguous'])][:8]
        return {'text': [say(ar, f"Several match \"{', '.join(meaning['ambiguous'])}\". Which one do you mean?",
                             f"أكثر من سجل يطابق \"{', '.join(meaning['ambiguous'])}\". تقصد مين؟")],
                'choices': [{'label': o, 'text': o} for o in options], 'asking': True}
    if intent == 'help':
        return {'text': HELP_AR if ar else HELP_EN}
    if intent in ('room_schedule', 'instructor_schedule', 'group_schedule', 'course_schedule', 'free_rooms') and not run:
        return {'text': [say(ar, 'There is no completed, valid teaching timetable yet. Ask me to generate one.', 'لا يوجد جدول مكتمل وصالح بعد. اطلب مني إنشاء جدول.')],
                'action': {'type': 'open', 'page': 'timetable', 'label': say(ar, 'Open Timetable', 'فتح الجدول')}}
    source = None
    if run:
        source = say(ar, f"From the {'published' if run['published'] else 'latest valid'} timetable"
                         f"{' (inputs changed since)' if run['stale'] else ''}.",
                     f"من الجدول {'المنشور' if run['published'] else 'الأحدث الصالح'}{' (تغيرت المدخلات بعده)' if run['stale'] else ''}.")
    if intent == 'free_rooms':
        lines, ask = free_rooms(view, slots, ar)
        return {'text': lines + [source]} if lines else {'text': [ask], 'asking': True}
    kind = {'room_schedule': 'rooms', 'instructor_schedule': 'instructors', 'group_schedule': 'groups', 'course_schedule': 'courses'}.get(intent)
    if kind:
        ids = slots.get(kind) or []
        if not ids:
            what = {'rooms': ('room', 'القاعة'), 'instructors': ('instructor', 'المحاضر'), 'groups': ('group', 'المجموعة'), 'courses': ('course', 'المقرر')}[kind]
            return {'text': [say(ar, f'Which {what[0]}? I could not find it by that name or code.', f'أي {what[1]}؟ لم أجده بهذا الاسم أو الرمز.')], 'asking': True}
        names = {by_id(view)[i]['data'].get('name') for i in ids}
        if kind == 'courses' and len(names) == 1:
            # Sections of one course (one record per group): one list, each line naming its section.
            order = view['calendar']['days']
            mine = sorted((s for s in view['sessions'] if s['activity_id'] in set(ids) and (not slots.get('days') or s['day'] in slots['days'])),
                          key=lambda s: (order.index(s['day']) if s['day'] in order else 9, s['start_minute'], s['code']))
            course = next(iter(names))
            lines = [say(ar, f"{course}: {len(mine)} sessions in {len(ids)} sections", f"{course}: {len(mine)} محاضرة في {len(ids)} شعبة")]
            lines += [f"• {s['code']} · " + describe(s, ar, ('room', 'instructor')) for s in mine[:40]]
            if len(mine) > 40:
                lines.append(say(ar, f'… and {len(mine) - 40} more.', f'… و{len(mine) - 40} أخرى.'))
            return {'text': lines + [source]}
        if len(ids) > 3:
            names = [by_id(view)[i]['data'].get('code') or by_id(view)[i]['data'].get('name') for i in ids[:8]]
            return {'text': [say(ar, f"That matches {len(ids)} records. Which one do you mean?", f"هذا يطابق {len(ids)} سجلات. تقصد أي واحد؟")],
                    'choices': [{'label': n, 'text': n} for n in names], 'asking': True}
        lines = []
        for ident in ids:
            lines += availability(view, kind, ident, slots, ar)
        return {'text': lines + [source]}
    if intent == 'generate_timetable':
        question = generation_question(slots, view, ar)
        if question:
            return question
        scope = None if slots.get('everything') else scope_of(slots, view['records'])
        codes = {r['id']: r['data'].get('code') or r['data'].get('name') for r in view['records'] if r['kind'] == 'groups'}
        named = [codes[s['group']] if s.get('group') else s['programme'] + (say(ar, ' year ', ' سنة ') + str(s['year']) if s['year'] else '') for s in scope or []]
        what = say(ar, 'the whole university', 'الجامعة كلها') if scope is None else ', '.join(named)
        last = view['last_status']
        if last and last['status'] in ('queued', 'running'):
            return {'text': [say(ar, 'A timetable is already being generated. Wait for it to finish first.', 'يوجد جدول قيد الإنشاء الآن. انتظر حتى ينتهي.')],
                    'action': {'type': 'open', 'page': 'timetable', 'label': say(ar, 'Watch it', 'متابعة')}}
        shared = say(ar, ' Lectures it shares with other groups are placed for those groups too.', ' المحاضرات المشتركة مع مجموعات أخرى تُجدول لهم أيضاً.') if scope and any(s.get('group') for s in scope) else ''
        return {'text': [say(ar, f'I will generate a draft timetable for {what}{" only" if scope else ""}. It runs on the solver and appears on the Timetable page; nothing is published.',
                             f'سأنشئ مسودة جدول لـ {what}{" فقط" if scope else ""}. تعمل على المحلل وتظهر في صفحة الجدول؛ لا يُنشر شيء.') + shared],
                'action': {'type': 'generate', 'scope': scope, 'label': say(ar, 'Generate', 'إنشاء'), 'version': view['version'],
                           **({'filter': {'group': scope[0]['group']}} if scope and len(scope) == 1 and scope[0].get('group') else
                              {'filter': {'major': scope[0]['programme'], 'year': str(scope[0]['year']) if scope[0]['year'] else ''}} if scope and len(scope) == 1 else {})}}
    if intent == 'exam_timetable':
        kind = slots.get('exam_kind') or 'midterm'
        dates = slots.get('dates') or []
        if len(dates) < 2:
            return {'text': [say(ar, f'Which dates should the {kind} timetable cover? For example "from 20 Dec to 31 Dec".',
                                 'ما هي تواريخ فترة الامتحانات؟ مثلاً "من 20 ديسمبر إلى 31 ديسمبر".')], 'asking': True}
        body = {'kind': kind, 'start_date': dates[0], 'end_date': dates[1]}
        if kind == 'final':
            body['skip'] = [f'{c}:makeup' for c in view['second_chance']]  # as on the Exams page: second chances start unticked
        if kind == 'quiz':
            body.update(quiz_number=slots.get('quiz_number') or 1, quiz_minutes=min(60, max(15, round((slots.get('quiz_minutes') or 30) / 15) * 15)))
        title = {'final': say(ar, 'finals (with second-chance midterms in the first slot)', 'النهائي (والفرصة الثانية في أول فترة)'),
                 'midterm': say(ar, 'midterms', 'منتصف الفصل'),
                 'quiz': say(ar, f"quiz {body.get('quiz_number')} ({body.get('quiz_minutes')} min)", f"الاختبار القصير {body.get('quiz_number')} ({body.get('quiz_minutes')} دقيقة)")}[kind]
        return {'text': [say(ar, f'I will create a draft exam timetable for the {title}, {dates[0]} to {dates[1]}, Fridays off, all courses with that exam.',
                             f'سأنشئ مسودة جدول امتحانات {title} من {dates[0]} إلى {dates[1]}، بدون أيام الجمعة، لكل المقررات.'),
                         say(ar, 'Second-chance midterms are left out; add them on the Exams page.', 'الفرص الثانية غير مضمنة؛ أضفها من صفحة الامتحانات.') if kind == 'final' else ''],
                'action': {'type': 'exam', 'body': body, 'label': say(ar, 'Create exam timetable', 'إنشاء جدول الامتحانات'), 'version': view['version']}}
    if intent == 'download_pdf':
        if not run:
            return {'text': [say(ar, 'There is no valid timetable to download yet.', 'لا يوجد جدول صالح للتحميل بعد.')]}
        params = {}
        if slots.get('groups'):
            params['group'] = slots['groups'][0]
        else:
            if slots.get('year'):
                params['year'] = str(slots['year'])
            if slots.get('programmes'):
                params['major'] = slots['programmes'][0]
        from urllib.parse import urlencode
        label = (by_id(view)[params['group']]['data'].get('code') if 'group' in params else ' '.join(x for x in (params.get('major'), f"year {params['year']}" if params.get('year') else '') if x)) or say(ar, 'the whole timetable', 'الجدول كله')
        return {'text': [say(ar, f'Here is the PDF for {label}.', f'هذا ملف PDF لـ {label}.'), source],
                'action': {'type': 'download', 'url': f"/api/schedules/{run['id']}/timetable.pdf" + ('?' + urlencode(params) if params else ''), 'label': say(ar, 'Download PDF', 'تحميل PDF')}}
    if intent == 'status':
        last = view['last_status']
        if not last:
            return {'text': [say(ar, 'No timetable has been generated yet.', 'لم يُنشأ أي جدول بعد.')]}
        lines = [say(ar, f"Latest run: {last['status']}, {last['sessions']} sessions, validation {'passed' if last['passed'] else 'not passed' if last['passed'] is False else 'pending'}.",
                     f"آخر تشغيل: {last['status']}، {last['sessions']} محاضرة، التحقق {'ناجح' if last['passed'] else 'غير ناجح' if last['passed'] is False else 'قيد الانتظار'}.")]
        if run:
            lines.append(say(ar, f"Timetable in use: {'published' if run['published'] else 'not published'}, {run['sessions']} sessions{', inputs changed since' if run['stale'] else ''}.",
                             f"الجدول المستخدم: {'منشور' if run['published'] else 'غير منشور'}، {run['sessions']} محاضرة{'، تغيرت المدخلات بعده' if run['stale'] else ''}."))
        if view['exam_run']:
            lines.append(say(ar, f"Latest exam timetable: {view['exam_run']['kind']}, {view['exam_run']['status']}.", f"آخر جدول امتحانات: {view['exam_run']['kind']}، {view['exam_run']['status']}."))
        return {'text': lines, 'action': {'type': 'open', 'page': 'timetable', 'label': say(ar, 'Open Timetable', 'فتح الجدول')}}
    return {'text': [say(ar, "I didn't understand that.", 'لم أفهم ذلك.')], 'unknown': True}


CAN_EN = ['Is room A3.128 free on Sunday at 10:00?', "Dr. Mohamed Fawzy's schedule on Tuesday", 'Free labs on Monday 11:30',
          'Add a new instructor', 'Add a new room', 'Add a student group', 'Generate a timetable', 'Create an exam timetable', 'Status of the latest run']
CAN_AR = ['هل قاعة A3.128 فاضية يوم الأحد الساعة 10؟', 'جدول دكتور محمد فوزي يوم الثلاثاء', 'أضف محاضر جديد', 'أضف قاعة جديدة', 'أضف مجموعة طلاب',
          'اعمل جدول', 'اعمل جدول امتحانات', 'حالة آخر تشغيل']
HELP_EN = ['I can answer questions about the current timetable and start work for you. Try:',
           '• "Is room A3.128 free on Sunday at 10:00?"', '• "Free labs on Monday 11:30 for 30 students"',
           '• "Dr. Mohamed Fawzy\'s schedule on Tuesday"', '• "What does BA Y3 G7 have on Wednesday?"', '• "When is Math I?"',
           '• "Generate the timetable for BA year 3"', '• "Create the finals timetable from 20 Dec to 31 Dec"',
           '• "Download the PDF for INF1-G7"', '• "Status of the latest run"',
           '• "Add a new instructor" / "Add room C7.201 with 40 seats" / "Add a student group"']
HELP_AR = ['أجيب عن أسئلة الجدول الحالي وأبدأ العمل نيابة عنك. جرّب:', '• "هل قاعة A3.128 فاضية يوم الأحد الساعة 10؟"',
           '• "معامل فاضية يوم الاثنين 11:30"', '• "جدول دكتور محمد فوزي يوم الثلاثاء"', '• "اعمل جدول BA سنة 3"',
           '• "اعمل جدول النهائي من 20 ديسمبر إلى 31 ديسمبر"', '• "نزل PDF لـ INF1-G7"', '• "أضف محاضر جديد"']


# ----------------------------------------------------------------------------- the local model
MODEL_SCHEMA = {'type': 'object', 'additionalProperties': False,
                'required': ['intent', 'record_kind', 'room', 'instructor', 'group', 'programme', 'year', 'course', 'days', 'start_time', 'end_time', 'exam_kind', 'start_date', 'end_date', 'whole_university'],
                'properties': {'intent': {'type': 'string', 'enum': [*INTENTS, 'unknown']},
                               'record_kind': {'type': ['string', 'null'], 'enum': ['instructors', 'rooms', 'groups', 'courses', None]},
                               'room': {'type': ['string', 'null']}, 'instructor': {'type': ['string', 'null']}, 'group': {'type': ['string', 'null']},
                               'programme': {'type': ['string', 'null']}, 'year': {'type': ['integer', 'null']}, 'course': {'type': ['string', 'null']},
                               'days': {'type': 'array', 'items': {'type': 'string', 'enum': ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']}},
                               'start_time': {'type': ['string', 'null']}, 'end_time': {'type': ['string', 'null']},
                               'exam_kind': {'type': ['string', 'null'], 'enum': ['quiz', 'midterm', 'final', None]},
                               'start_date': {'type': ['string', 'null']}, 'end_date': {'type': ['string', 'null']}, 'whole_university': {'type': 'boolean'}}}
MODEL_PROMPT = """You route messages from a university timetabling administrator (English, Arabic or Egyptian Arabic) to one intent of a scheduling website. Reply only with the JSON object.
Intents: room_schedule (a room's sessions or whether it is free), free_rooms (which rooms are free at a time), instructor_schedule, group_schedule (a student group), course_schedule (when a course meets), generate_timetable (create a teaching timetable for a programme/year or the whole university), exam_timetable (create quiz/midterm/final exam timetable), download_pdf, status (latest generation run), create_record (add a new instructor, room, student group or course; set record_kind), help, unknown.
Copy names and codes exactly as the message writes them; translate Arabic day names to English; times as HH:MM 24-hour; dates as YYYY-MM-DD (the current year is {year}). Use null when the message does not say. Programmes known: {programmes}."""


def model_settings():
    if os.environ.get('JADWAI_AI_ENABLED', '').lower() != 'true' or os.environ.get('JADWAI_AI_PROVIDER', '').lower() != 'local':
        return None
    from app.local_provider import DEFAULT_MODEL, DEFAULT_URL
    return os.environ.get('JADWAI_LOCAL_MODEL', DEFAULT_MODEL), os.environ.get('JADWAI_LOCAL_URL', DEFAULT_URL).rstrip('/'), float(os.environ.get('JADWAI_LOCAL_TIMEOUT_SECONDS', '180'))


async def model_understand(raw, view, *, transport=None):
    """The local model maps the message to an intent with names as written; resolution stays here."""
    settings = model_settings()
    if not settings:
        return None
    model, url, timeout = settings
    payload = {'model': model, 'stream': False, 'format': MODEL_SCHEMA, 'keep_alive': '30m', 'options': {'temperature': 0, 'seed': 42, 'num_ctx': 4096},
               'messages': [{'role': 'system', 'content': MODEL_PROMPT.format(year=date.today().year, programmes='; '.join(programmes(view['records'])))},
                            {'role': 'user', 'content': raw}]}
    try:
        async with httpx.AsyncClient(transport=transport, timeout=timeout, trust_env=False, follow_redirects=False) as client:
            response = await client.post(url + '/api/chat', json=payload)
        data = json.loads(response.json()['message']['content']) if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(data, dict) or data.get('intent') not in (*INTENTS, 'unknown'):
        return None
    # Rebuild a message from the model's fields and let the built-in resolver find the records.
    parts = [data.get(k) for k in ('room', 'instructor', 'group', 'course') if isinstance(data.get(k), str)]
    if isinstance(data.get('programme'), str):
        parts.append(data['programme'])
    if isinstance(data.get('year'), int):
        parts.append(f"year {data['year']}")
    text = normalise(' '.join(parts))
    records = view['records']
    found = {k: [r['id'] for r in find_records(text, records, k)[0]] if text else [] for k in ('rooms', 'instructors', 'courses')}
    progs = find_programme(text, records)
    year = data['year'] if isinstance(data.get('year'), int) else None
    to_min = lambda t: int(t[:2]) * 60 + int(t[3:5]) if isinstance(t, str) and re.fullmatch(r'\d{2}:\d{2}', t) else None
    start, end = to_min(data.get('start_time')), to_min(data.get('end_time'))
    slots = {**found, 'groups': [g['id'] for g in find_group(text, records, progs, year)], 'programmes': progs, 'year': year,
             'days': [d for d in data.get('days') or [] if d in view['calendar']['days']],
             'window': (start, end if end and end > start else start + 1) if start is not None else None,
             'exam_kind': data.get('exam_kind'), 'dates': [d for d in (data.get('start_date'), data.get('end_date')) if isinstance(d, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', d)],
             'everything': bool(data.get('whole_university')), 'lab': 'lab' in normalise(raw), 'seats': None}
    if data['intent'] == 'create_record':
        kind = data.get('record_kind') if data.get('record_kind') in ('instructors', 'rooms', 'groups', 'courses') else None
        return {'intent': 'create_record', 'slots': {'kind': kind, 'form': first_fill(kind, raw, normalise(raw), view) if kind in ('instructors', 'rooms', 'groups') else {}}, 'ambiguous': []}
    return {'intent': data['intent'], 'slots': slots, 'ambiguous': []}


# ----------------------------------------------------------------------------- the endpoint
@router.get('/configuration')
def configuration(user=Depends(administrator)):
    settings = model_settings()
    return {'model': settings[0] if settings else None, 'local_model': bool(settings)}


@router.post('')
async def ask(body: Ask, user=Depends(administrator), db=Depends(db_session)):
    view = view_of(db)
    db.commit()  # release the workspace lock before any model call; answers use the copy read above
    ar = bool(ARABIC.search(body.text))
    meaning = understand(body.text, view, body.previous)
    source = 'built-in'
    if meaning['intent'] == 'unknown' and body.use_model:
        model_meaning = await model_understand(body.text, view)
        if model_meaning and model_meaning['intent'] != 'unknown':
            meaning, source = model_meaning, 'local-model'
    reply = answer(meaning, view, ar)
    if reply.get('unknown'):
        settings = model_settings()
        if settings and not body.use_model:
            reply['text'].append(say(ar, f'Asking the local model ({settings[0]})…', f'جارٍ سؤال النموذج المحلي ({settings[0]})…'))
            reply['retry_with_model'] = True
        else:
            reply['text'] = [say(ar, "I can't do that yet, or I didn't understand it. Here is what I can do; pick one or rephrase:",
                                 'لا أستطيع ذلك بعد، أو لم أفهمه. هذا ما أقدر عليه؛ اختر أو أعد الصياغة:')]
            reply['choices'] = [{'label': x, 'text': x} for x in (CAN_AR if ar else CAN_EN)]
    keep = meaning if meaning['intent'] not in ('unknown',) else body.previous
    remembered = None if reply.get('forget') else {'intent': keep['intent'], 'slots': keep['slots'], **({'asking': True} if reply.get('asking') else {})} if keep else None
    return {'text': [line for line in reply['text'] if line], 'action': reply.get('action'), 'retry_with_model': reply.get('retry_with_model', False),
            'choices': reply.get('choices') or [], 'meaning': remembered, 'source': source, 'run': view['run']}
