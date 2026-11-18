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
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select
from app.dependencies import administrator, db_session, fail
from uuid import uuid4
from app.models import AssistantChat, AssistantMessage, CourseCatalog, ExamRun, Record, Rule, ScheduleRun, User, Workspace, utcnow
from app.rule_parser import ARABIC_DIGITS, DAYS, TIME, days_in, find_records, hour, mentions, normalise, plain, times
from app.schemas import Strict
from app.solver import MAX_SESSIONS
from app.assistant_records import KIND_WORDS, converse, fill, first_fill, record_kind
from app.assistant_tasks import account_answer, answer_task, understand_task

router = APIRouter(prefix='/api/assistant')
ARABIC = re.compile(r'[؀-ۿ]')
INTENTS = ('room_schedule', 'free_rooms', 'instructor_schedule', 'group_schedule', 'course_schedule',
           'generate_timetable', 'exam_timetable', 'download_pdf', 'status', 'help', 'create_record', 'publish', 'unpublish')
TASKS = ('open_page', 'cancel_run', 'rename_run', 'statistics', 'export_csv', 'input_checks', 'exam_pdf', 'exam_when', 'move_session', 'lock_session',
         'create_account', 'reset_account', 'list_accounts', 'list_rules', 'remove_rule', 'approve_rules', 'add_rule', 'delete_record', 'edit_record', 'record_info',
         'create_course', 'course_add', 'fix_problems', 'split_group', 'improve_schedule', 'programme_info', 'show_run')
INTENTS = INTENTS + TASKS
CANCEL_WORDS = ('cancel', 'never mind', 'nevermind', 'forget it', 'stop', 'الغاء', 'إلغاء', 'خلاص', 'سيبك', 'انسى')


class Screen(Strict):
    page: str = Field(max_length=30)
    run_id: str | None = Field(default=None, max_length=36)
    group: str | None = Field(default=None, max_length=36)
    year: str | None = Field(default=None, max_length=20)
    major: str | None = Field(default=None, max_length=100)
    query: str | None = Field(default=None, max_length=100)


class Ask(Strict):
    text: str = Field(min_length=1, max_length=2000)
    previous: dict | None = None  # without a chat: the last understood message, for follow-ups ("and on Monday?")
    chat_id: str | None = Field(default=None, max_length=36)  # the chat this message belongs to; it keeps the context
    use_model: bool = False       # ask the local model when the built-in patterns don't recognise it
    screen: 'Screen | None' = None  # what the admin is looking at: the page, and on the Timetable page the draft and filters


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


def newest_part(db, ident):
    """A run, or the newest run built on top of it (the later parts of a whole-university build)."""
    row = db.get(ScheduleRun, ident) if ident else None
    for _ in range(20):
        child = row and db.scalar(select(ScheduleRun).where(ScheduleRun.parent_run_id == row.id).order_by(ScheduleRun.created_at.desc()).limit(1))
        if not child:
            break
        row = child
    return row


def view_of(db, run_id=None, talked_about=None, exam_id=None):
    """Everything an answer needs, read once so the DB lock can be released before a model call.

    run_id is the draft on the Timetable page; talked_about the one this chat is about (for example the one it
    just generated), used when no timetable is on screen."""
    ws = db.get(Workspace, 1)
    from app.schedules import continue_chain
    continue_chain(db, ws)  # a whole-university build moves on to its next part
    records = [{'id': r.id, 'kind': r.kind, 'data': r.data} for r in db.scalars(select(Record).order_by(Record.id))]
    # The draft the admin is looking at on the Timetable page, when it can be read; otherwise the published one.
    shown = db.get(ScheduleRun, run_id) if run_id else newest_part(db, talked_about)
    readable = bool(shown and shown.status == 'completed' and (shown.result or {}).get('validation', {}).get('passed'))
    on_screen = readable and bool(run_id)
    run = shown if readable else latest_run(db)
    # The timetable the admin means is still being made (or did not come out valid): say so instead of using another.
    meant = None if readable or not shown else {'id': shown.id, 'status': shown.status, 'name': shown.name,
                                                'passed': (shown.result or {}).get('validation', {}).get('passed')}
    sessions = []
    if run:
        # The run's own snapshot names the records it scheduled (they may have changed since).
        snap = {r['id']: r for r in run.snapshot['records']}
        for a in run.result['assignments']:
            act = snap.get(a['activity_id'], {})
            sessions.append({**a, 'course': act.get('name', '?'), 'code': act.get('code', ''), 'type': act.get('activity_type', ''),
                             'groups': act.get('group_ids', []), 'room': snap.get(a.get('room_id'), {}).get('code', ''),
                             'instructor': snap.get(a.get('instructor_id'), {}).get('name', '')})
    exams = db.get(ExamRun, exam_id) if exam_id else db.scalar(select(ExamRun).order_by(ExamRun.created_at.desc()).limit(1))
    from app.partial_plan import complete as part_complete
    return {'calendar': {'days': ws.days, 'start_hour': ws.start_hour, 'end_hour': ws.end_hour,
                         'period_minutes': ws.period_minutes, 'teaching_periods': ws.teaching_periods or []},
            'workspace': {k: getattr(ws, k) for k in ('name', 'term', 'timezone', 'days', 'start_hour', 'end_hour', 'period_minutes', 'teaching_periods', 'realism_policy', 'start_date', 'end_date')},
            'records': records, 'version': ws.version, 'sessions': sessions,
            'second_chance': [c.id for c in db.scalars(select(CourseCatalog)) if c.second_chance],
            'catalog': [{'id': c.id, 'name': c.name, 'code': c.code, 'eligibility': c.eligibility, 'group_ids': c.group_ids, 'quiz_count': c.quiz_count,
                         'second_chance': c.second_chance, 'expected_students': c.expected_students} for c in db.scalars(select(CourseCatalog))],
            'published_id': db.scalar(select(ScheduleRun.id).where(ScheduleRun.published_at.isnot(None))),
            'newest': newest_valid(db, ws),
            'users': [{'id': u.id, 'email': u.email, 'name': u.name, 'role': u.role, 'active': u.active, 'version': u.version, 'group_id': u.group_id, 'instructor_id': u.instructor_id, 'advising_student_id': u.advising_student_id} for u in db.scalars(select(User))],
            'rules': [{'id': r.id, 'status': r.status, **r.data} for r in db.scalars(select(Rule))],
            'exams': exam_rows(db),
            'run': {'id': run.id, 'name': run.name, 'published': bool(run.published_at), 'stale': run.input_version != ws.version, 'on_screen': on_screen, 'talked_about': readable and not on_screen,
                    'complete': part_complete(run.snapshot), 'scope': (run.snapshot.get('plan') or {}).get('scope'),
                    'created_at': run.created_at.isoformat(), 'sessions': len(run.result['assignments']),
                    'kept': len((run.snapshot.get('plan') or {}).get('fixed') or [])} if run else None,
            'exam_run': {'id': exams.id, 'status': (exams.result or {}).get('status'), 'kind': (exams.snapshot.get('settings') or {}).get('kind'),
                         'published': bool(exams.published_at), 'stale': exams.input_version != ws.version, 'halls': 'halls' in exams.snapshot, 'name': exams.name, 'courses': len(exams.snapshot.get('courses') or []), 'start_date': (exams.snapshot.get('settings') or {}).get('start_date'), 'end_date': (exams.snapshot.get('settings') or {}).get('end_date')} if exams else None,
            'published_exam': db.scalar(select(ExamRun.id).where(ExamRun.published_at.isnot(None))),
            'last_status': last_status(db), 'meant': meant, 'timezone': ws.timezone,
            'published_activities': published_activities(db)}


def published_activities(db):
    """The activities the published teaching timetable places (to see what a newer draft adds)."""
    row = db.scalar(select(ScheduleRun).where(ScheduleRun.published_at.isnot(None)))
    return sorted({a['activity_id'] for a in (row.result or {}).get('assignments') or []}) if row and row.status == 'completed' else None


def newest_valid(db, ws):
    """The most recent completed, valid draft: what "publish it" means when no timetable is on screen."""
    from app.partial_plan import complete
    for row in db.scalars(select(ScheduleRun).where(ScheduleRun.status == 'completed').order_by(ScheduleRun.created_at.desc()).limit(10)):
        if (row.result or {}).get('validation', {}).get('passed'):
            return {'id': row.id, 'published': bool(row.published_at), 'stale': row.input_version != ws.version, 'complete': complete(row.snapshot),
                    'scope': (row.snapshot.get('plan') or {}).get('scope'), 'sessions': len(row.result['assignments']), 'on_screen': False,
                    'talked_about': False, 'created_at': row.created_at.isoformat(), 'name': row.name, 'kept': len((row.snapshot.get('plan') or {}).get('fixed') or [])}
    return None


def exam_rows(db):
    """Exams of the published exam timetable, otherwise of the latest completed one."""
    row = db.scalar(select(ExamRun).where(ExamRun.published_at.isnot(None))) or \
        next((r for r in db.scalars(select(ExamRun).order_by(ExamRun.created_at.desc()).limit(5)) if (r.result or {}).get('status') == 'completed'), None)
    return (row.result or {}).get('assignments', []) if row else []


def last_status(db):
    row = db.scalar(select(ScheduleRun).order_by(ScheduleRun.created_at.desc()).limit(1))
    if not row:
        return None
    return {'id': row.id, 'status': row.status, 'passed': (row.result or {}).get('validation', {}).get('passed'),
            'sessions': len((row.result or {}).get('assignments') or []), 'scope': (row.snapshot or {}).get('plan', {}).get('scope'),
            'chain': (row.snapshot or {}).get('chain'), 'chain_stopped': (row.result or {}).get('chain_stopped')}


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
    if found:
        return found
    # Part of the name: two of its words together ("Computer Science" for Applied Computer Science & Informatics),
    # or one word no other programme has ("Security", "Marketing").
    names = programmes(records)
    words = {p: [w for w in re.findall(r'[a-z\u0600-\u06FF]+', normalise(p)) if len(w) >= 3 and w not in ('and', 'the')] for p in names}
    counts = {}
    for ws in words.values():
        for w in set(ws):
            counts[w] = counts.get(w, 0) + 1
    for p, ws in words.items():
        pairs = [f'{a} {b}' for a, b in zip(ws, ws[1:])]
        if any(mentions(text, pair) for pair in pairs) or any(counts[w] == 1 and len(w) >= 5 and mentions(text, w) for w in ws):
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


ORDINALS = {'first': 1, '1st': 1, 'second': 2, '2nd': 2, 'third': 3, '3rd': 3, 'fourth': 4, '4th': 4, 'fifth': 5, '5th': 5, 'sixth': 6, '6th': 6,
            'الاولي': 1, 'اول': 1, 'الاول': 1, 'الثانيه': 2, 'الثانية': 2, 'تاني': 2, 'تانيه': 2, 'التانية': 2, 'الثالثه': 3, 'الثالثة': 3, 'تالت': 3, 'التالتة': 3,
            'الرابعه': 4, 'الرابعة': 4, 'رابع': 4, 'الخامسه': 5, 'الخامسة': 5, 'خامس': 5}
PERIOD_NOUNS = r'(?:slot|period|session|class|lecture|block|فتره|فترة|حصه|حصة|سلوت)'


def period_of(text, calendar, bare=False):
    """The teaching period a message names: "first slot", "3rd period", "slot 2", "the last period", "الفترة التالتة".
    With bare=True a lone ordinal counts too ("to third on Sunday")."""
    periods = calendar.get('teaching_periods') or [{'start': m, 'end': m + calendar['period_minutes']}
                                                   for m in range(calendar['start_hour'] * 60, calendar['end_hour'] * 60, calendar['period_minutes'])]
    words = '|'.join(sorted(map(re.escape, ORDINALS), key=len, reverse=True))
    m = re.search(rf'(?<![\w])(last|اخر|الاخيره|الاخيرة)\s*{PERIOD_NOUNS}|{PERIOD_NOUNS}\s*(?:ال)?(last|الاخيره|الاخيرة)(?![\w])', text)
    if m:
        return periods[-1]
    m = re.search(rf'(?<![\w])({words})\s*{PERIOD_NOUNS}|{PERIOD_NOUNS}\s*(?:number\s*|رقم\s*)?(\d|{words})(?![\w])', text) or \
        (re.search(rf'(?<![\w])(?:the\s+)?({words})(?![\w])', text) if bare else None)
    if not m:
        return None
    word = next(g for g in m.groups() if g)
    n = int(word) if word.isdigit() else ORDINALS.get(word)
    return periods[n - 1] if n and 1 <= n <= len(periods) else None


def window(text, calendar, bare_period=False):
    """(start, end) minutes the message asks about, a single moment, or None for the whole day."""
    period = period_of(text, calendar, bare_period)
    if period:
        return period['start'], period['start'] + 1
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
UNPUBLISH_WORDS = ('unpublish', 'un-publish', 'take it down', 'take down', 'withdraw', 'retract', 'الغي النشر', 'ألغي النشر', 'إلغاء النشر', 'الغاء النشر', 'وقف النشر', 'شيل النشر')
PUBLISH_WORDS = ('publish', 'make it live', 'release it', 'go live', 'share it with students', 'انشر', 'نشر', 'انشره', 'انشرها', 'إنشر')
HELP_WORDS = ('help', 'what can you do', 'how do i', 'مساعدة', 'تقدر تعمل ايه', 'بتعمل ايه')
ROOM_HINT = ('room', 'hall', 'lab', 'قاعة', 'قاعه', 'معمل', 'مدرج')


def has(text, words):
    return any(w in text for w in words)


def H_course_create(text):
    return bool(re.search(r'\b(new course|create a course|add a course|course called|course named)\b|مقرر جديد', text))


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
    correction = re.match(r'^(?:no|nope|not that|i meant|i mean|actually|wrong|لا|لأ|مش ده|مش دي|قصدي|اقصد|أقصد)(?![\w])[\s,.!،]*', text)
    if correction and re.match(r'^no\s+(?:classes|lectures|class|sessions|teaching|more|gaps)\b', text):
        correction = None  # "no classes before 10" is a request, not "no, I meant…"
    if correction and previous and previous.get('intent') in INTENTS and previous['intent'] != 'create_record' and not asked:
        rest = text[correction.end():]
        # A different action named after the "no" is a new request, not a correction.
        other = has(rest, CREATE_WORDS + STATUS_WORDS) or (has(rest, PDF_WORDS) and previous['intent'] != 'download_pdf')
        if not other:
            # "No, this timetable" / "no, G8" / "I meant Monday": the same request, with what was corrected.
            old = dict(previous.get('slots') or {})
            new = {k: v for k, v in slots.items() if v}
            if re.search(r'(?<![\w])(this|current|here|on (?:my |the )?screen|showing|shown|open|هذا|هذه|ده|دي|الحالي|اللي قدامي|المعروض)(?![\w])', rest):
                for k in ('groups', 'programmes', 'year', 'everything'):
                    old.pop(k, None)  # "this one": what is on the screen, not what was named before
            return {'intent': previous['intent'], 'slots': {**old, **new}, 'ambiguous': ambiguous, 'follow_up': True}
    # A clear new request (a question, a timetable, a command) leaves a half-filled form instead of filling it.
    fresh_request = bool(re.search(r'^(?:is|are|what|when|who|which|where|how|does|do|هل|امتي|مين|ايه|فين|كام)\b', text) or text.endswith(('?', '؟'))
                         or (has(text, CREATE_WORDS) and has(text, ('timetable', 'schedule', 'جدول'))) or understand_task(raw, text, view))
    if asked and previous['intent'] == 'create_record' and new_record is None and not fresh_request:
        # Inside a create conversation every reply answers the question JAI asked.
        old = dict(previous.get('slots') or {})
        form, field = dict(old.get('form') or {}), old.get('field')
        old.pop('unreadable', None)
        if field == 'kind':
            kind = next((k for k, words in KIND_WORDS.items() if any(w in f' {text} ' or w.strip() == text for w in words)), None)
            return {'intent': 'create_record', 'slots': {**old, 'kind': kind, 'form': first_fill(kind, raw, text, view) if kind else {}, **({} if kind else {'unreadable': True})}, 'ambiguous': []}
        value = fill(field, raw, text, view, form) if field else None
        if value is None:
            return {'intent': 'create_record', 'slots': {**old, 'form': form, 'unreadable': True}, 'ambiguous': []}
        form[field] = value
        return {'intent': 'create_record', 'slots': {**old, 'form': form}, 'ambiguous': []}
    if asked and previous['intent'] == 'improve_schedule':
        # "Two free days" / "for BA5-G7" answers what JAI asked; the rest of the request is kept.
        from app.assistant_improve import goals_in, target_groups
        old = dict(previous.get('slots') or {})
        goals, groups = goals_in(text, view['calendar']), target_groups(text, view) if not old.get('groups') else []
        if goals or groups:
            return {'intent': 'improve_schedule', 'slots': {**old, 'goals': {**(old.get('goals') or {}), **goals}, 'groups': old.get('groups') or groups},
                    'ambiguous': [], 'follow_up': True}
    if asked and previous['intent'] == 'create_course' and new_record is None and not fresh_request:
        from app.assistant_courses import answer_field
        old = dict(previous.get('slots') or {})
        form = dict(old.get('form') or {})
        value = answer_field(old.get('field'), raw, text, view, form) if old.get('field') else None
        if isinstance(value, dict):
            form['_last'] = value
        elif value is not None:
            form[old['field']] = value
        return {'intent': 'create_course', 'slots': {**old, 'form': form, 'unreadable': value is None}, 'ambiguous': [], 'follow_up': True}
    if re.search(r'^(?:please\s+|can you\s+|could you\s+)?(?:add|put|enrol|enroll|include|assign|ضيف|اضف|أضف)\b', text):
        from app.assistant_courses import catalog_named
        if catalog_named(text, view) and not H_course_create(text):
            return {'intent': 'course_add', 'slots': {'raw': raw}, 'ambiguous': []}
    if new_record == 'courses':
        from app.assistant_courses import first_fill as course_fill
        return {'intent': 'create_course', 'slots': {'form': course_fill(raw, text, view)}, 'ambiguous': []}
    if asked and previous['intent'] in ('create_account', 'move_session', 'lock_session', 'remove_rule', 'reset_account') and new_record is None and \
            not (fresh_request and previous['intent'] == 'create_account' and (previous.get('slots') or {}).get('field') not in ('name', 'email')):
        old = dict(previous.get('slots') or {})
        if previous['intent'] == 'create_account' and old.get('field'):
            value = account_answer(old['field'], raw, text, view)
            form = dict(old.get('form') or {})
            if value is not None:
                form[old['field']] = value
                if old['field'] == 'instructor_id':
                    form.setdefault('name', next((r['data']['name'] for r in view['records'] if r['id'] == value), None))
            return {'intent': 'create_account', 'slots': {**old, 'form': form, 'unreadable': value is None}, 'ambiguous': [], 'follow_up': True}
        new_question = re.search(r'^(?:is|are|what|when|who|which|where|how|does|do|why|explain|but|هل|امتي|مين|ايه|فين|كام|ليه|لماذا)\b', text) or text.endswith(('?', '؟'))
        if previous['intent'] in ('move_session', 'lock_session') and not record_kind(text) and not new_question:
            # More detail: "to Monday 10:15" says where it goes; anything else narrows which session.
            from app.assistant_tasks import split_move
            more_source, more_target = split_move(raw if not re.match(r'^(?:to|الى|إلى)\s', text) else ' ' + raw)
            if re.match(r'^(?:to|الى|إلى)\s', text):
                more_source, more_target = '', re.sub(r'^\s*(?:to|الى|إلى)\s+', '', raw, flags=re.I)
            return {'intent': previous['intent'], 'slots': {**old, 'source': f"{old.get('source', '')} {more_source}".strip(),
                                                           'target': more_target or old.get('target', '')}, 'ambiguous': [], 'follow_up': True}
    if previous and previous.get('intent') == 'move_session' and re.search(r'^(?:why|how come|but|explain|ليه|لماذا|ازاي|اشمعنى)\b|why\b.*\?', text):
        # "Why is this a problem, these are other groups?": the same check, explained first.
        return {'intent': 'move_session', 'slots': {**(previous.get('slots') or {}), 'explain': True}, 'ambiguous': [], 'follow_up': True}
    if previous and previous.get('intent') == 'move_session' and re.search(
            r'other (?:options|times|slots)|alternatives?|what else|where (?:else|can it go)|suggest|options|بدائل|اختيارات|حلول|فين تاني', text):
        # "What are the other options?" after a move: times that work for that same session.
        return {'intent': 'move_session', 'slots': {**(previous.get('slots') or {}), 'target': ''}, 'ambiguous': [], 'follow_up': True}
    task = understand_task(raw, text, view) if new_record is None else None
    if task:
        return {**task, 'ambiguous': []}
    if new_record is not None:
        if new_record == '':
            return {'intent': 'create_record', 'slots': {'kind': None}, 'ambiguous': []}
        if new_record == 'groups':
            # "Create a new study group here": in the programme and year the chat was just about.
            from app.assistant_context import place_of
            form = {**place_of(text, view.get('memory') or {}), **first_fill(new_record, raw, text, view)}
            return {'intent': 'create_record', 'slots': {'kind': new_record, 'form': form}, 'ambiguous': []}
        return {'intent': 'create_record', 'slots': {'kind': new_record, 'form': first_fill(new_record, raw, text, view)}, 'ambiguous': []}
    # A short reply without a request of its own answers JAI's last question.
    answering = bool(previous and previous.get('intent') in INTENTS and previous.get('asking') and len(text.split()) <= 8
                     and not has(text, CREATE_WORDS + ASK_WORDS + SCHEDULE_WORDS + PDF_WORDS + STATUS_WORDS + HELP_WORDS)
                     and not any(has(text, w) for w in EXAM_WORDS.values()))
    if answering:
        # The answer to JAI's question ("BA5-G7", "all of them", "year 3", "20 Dec to 31 Dec") completes the previous request.
        old, new = previous.get('slots') or {}, {k: v for k, v in slots.items() if v}
        bare = re.fullmatch(r'(\d{1,2})', text)
        if bare and previous['intent'] == 'generate_timetable' and old.get('programmes'):
            # A bare number answers what was asked: the year, or once the year is known, the group number.
            if not old.get('year'):
                new['year'] = int(bare.group(1))
            else:
                text = f'g{bare.group(1)}'
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
    elif has(text, UNPUBLISH_WORDS):
        intent = 'unpublish'
        slots['exams'] = bool(exam) or has(text, ('exam', 'امتحان', 'امتحانات')) or bool(previous and previous.get('intent') == 'exam_timetable' and not has(text, ('teaching', 'weekly', 'تدريس', 'اسبوعي')))
    elif re.search(r'(?<![\w])(' + '|'.join(map(re.escape, PUBLISH_WORDS)) + r')(?![\w])', text):  # "publish", not "published"
        intent = 'publish'
        slots['exams'] = bool(exam) or has(text, ('exam', 'امتحان', 'امتحانات')) or bool(previous and previous.get('intent') == 'exam_timetable' and not has(text, ('teaching', 'weekly', 'تدريس', 'اسبوعي')))
        # "publish this group's schedule" / "publish G6 only": one group, not the whole draft.
        slots['one_group'] = bool(re.search(r"\b(?:this|that|the|one|its|their)\s+group|\bgroup'?s\b|\bonly\b|المجموعة|الجروب|فقط|بس", text))
    elif has(text, HELP_WORDS) and len(text) < 40:
        intent = 'help'
    elif exam and (has(text, CREATE_WORDS) or 'timetable' in text or 'schedule' in text or 'جدول' in text):
        intent = 'exam_timetable'
        scope_query = re.search(r'\bfor\s+(.+?)(?=\s+(?:from|between|on)\b|$)', text)
        if scope_query and not (progs or groups or courses) and not has(scope_query.group(1), ('all', 'whole', 'university', 'everyone')):
            slots['scope_query'] = scope_query.group(1)
        slots['include_makeups'] = has(text, ('include second-chance', 'include second chance', 'with second-chance', 'with second chance', 'include makeup', 'including makeup', 'مع الفرصة الثانية', 'مع فرصه تانيه'))
        slots['exclude_fridays'] = not has(text, ('include fridays', 'including fridays', 'fridays too', 'with fridays', 'شامل الجمعة', 'بما فيها الجمعة'))
        slots['use_halls'] = not has(text, ('without halls', 'no halls', 'dates and times only', 'بدون قاعات'))
        slots['assign_invigilators'] = not has(text, ('without invigilators', 'no invigilators', 'بدون مراقبين'))
        daily = re.search(r'(\d+)\s+exams?\s+(?:per|a|each)\s+day', text)
        if daily:
            slots['max_exams_per_cohort_day'] = int(daily.group(1))
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
    elif previous and previous.get('intent') in INTENTS and (days or span) and not re.match(
            r'^(?:please\s+)?(?:move|reschedule|shift|swap|lock|delete|remove|add|create|make|generate|change|set|split|publish|انقل|حرك|اعمل|احذف|ضيف|غير)\b', text):
        # A follow-up such as "and on Monday?" keeps the previous subject.
        old = previous.get('slots') or {}
        # "What about Sunday?" keeps the time asked about; "who is in it on Monday?" means the whole day.
        listing = has(text, SCHEDULE_WORDS + ('who ', 'what ', 'مين', 'ايه'))
        return {'intent': previous['intent'], 'slots': {**old, 'days': days or old.get('days', []), 'window': span or (None if listing and days else old.get('window'))},
                'ambiguous': [], 'follow_up': True}
    # Only a name, no question words, day or time, in a longer sentence: probably not a question about it.
    weak = intent in ('room_schedule', 'instructor_schedule', 'group_schedule', 'course_schedule') and not (days or span) \
        and not has(text, ASK_WORDS + SCHEDULE_WORDS + ('when', 'where', 'who', 'امتى', 'امتي', 'فين', 'مين')) and len(text.split()) > 5
    return {'intent': intent or 'unknown', 'slots': slots, 'ambiguous': ambiguous, **({'weak': True} if weak else {})}


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
        # Always programme, then year, then group; a step is skipped only when the admin already said it.
        if years:
            only = say(ar, f' Only year {years[0]} has groups.', f' سنة {years[0]} فقط بها مجموعات.') if len(years) == 1 else ''
            return {'text': [say(ar, f'Which year of {progs[0]}?', f'أي سنة في {progs[0]}؟') + only],
                    'choices': [{'label': say(ar, f'Year {y}', f'سنة {y}'), 'text': f'year {y}'} for y in years]
                               + ([{'label': say(ar, 'All years', 'كل السنين'), 'text': 'all years'}] if len(years) > 1 else []),
                    'asking': True}
    if len(progs) == 1 and year and not slots.get('all_groups'):
        mine = sorted((g for g in groups if g['data'].get('major') == progs[0] and g['data'].get('year') == year),
                      key=lambda g: (len(g['data'].get('code', '')), g['data'].get('code', '')))
        if not mine:
            years = sorted({g['data'].get('year') for g in groups if g['data'].get('major') == progs[0] and g['data'].get('year')})
            slots.pop('year', None)
            return {'text': [say(ar, f"{progs[0]} has no groups in year {year}. Which year?", f"لا توجد مجموعات في {progs[0]} سنة {year}. أي سنة؟")],
                    'choices': [{'label': say(ar, f'Year {y}', f'سنة {y}'), 'text': f'year {y}'} for y in years], 'asking': True}
        if len(mine) > 1:
            whole = f"{progs[0]} {say(ar, 'year', 'سنة')} {year}"
            return {'text': [say(ar, f'All {len(mine)} groups of {whole}, or one group?', f'كل الـ{len(mine)} مجموعات في {whole}، ولا مجموعة واحدة؟')],
                    'choices': [{'label': say(ar, f'All of year {year}', f'كل سنة {year}'), 'text': 'all of them'}] + [{'label': g['data']['code'], 'text': g['data']['code']} for g in mine[:15]],
                    'asking': True}
    return None


def local_time(stamp, zone):
    """"21:24" for an ISO time, in the university's time zone."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    if not stamp:
        return ''
    try:
        return datetime.fromisoformat(stamp).astimezone(ZoneInfo(zone or 'UTC')).strftime('%H:%M')
    except (ValueError, KeyError):
        return stamp[11:16]


def filtered_view(view):
    """(name, sessions) of the group, year or programme the Timetable page is filtered to, or None when it shows everything."""
    seen = view.get('screen') or {}
    groups = [r for r in view['records'] if r['kind'] == 'groups']
    if seen.get('group'):
        chosen = [g for g in groups if g['id'] == seen['group']]
        name = chosen[0]['data'].get('code') or chosen[0]['data'].get('name') if chosen else None
    elif seen.get('year') or seen.get('major'):
        chosen = [g for g in groups if (not seen.get('year') or str(g['data'].get('year') or 'unassigned') == seen['year'])
                  and (not seen.get('major') or (g['data'].get('major') or '__unassigned') == seen['major'])]
        name = ' '.join(x for x in [seen.get('major') if seen.get('major') != '__unassigned' else '',
                                    f"year {seen['year']}" if seen.get('year') not in (None, '', 'unassigned') else ''] if x) or None
    else:
        return None
    if not chosen or not name:
        return None
    ids = {g['id'] for g in chosen}
    return name, sum(1 for s in view['sessions'] if ids & set(s.get('groups') or []))


def publish_groups(chosen, run, view, ar):
    """Publish only some groups' weeks from a draft into the published timetable; everyone else keeps theirs."""
    names = {r['id']: r['data'].get('code') or r['data'].get('name') for r in view['records'] if r['kind'] == 'groups'}
    who = ', '.join(names.get(g, '?') for g in chosen)
    if run['stale']:
        return {'text': [say(ar, f"The data changed since this draft was made, so {who}'s week in it may no longer be valid. Generate a new draft for {who}, then publish it.",
                             f"تغيرت البيانات بعد إنشاء هذه المسودة، لذلك قد لا يكون أسبوع {who} فيها صالحاً. أنشئ مسودة جديدة لـ {who} ثم انشرها.")],
                'choices': [{'label': say(ar, f'Generate {who}', f'إنشاء {who}'), 'text': f'generate a timetable for {who}'}]}
    have = view.get('published_activities')
    if have is None:
        return {'text': [say(ar, f"Nothing is published yet, so {who}'s week can't be published on its own: the first published timetable has to be complete. Publish the whole draft?",
                             f"لا يوجد جدول منشور بعد، لذلك لا يمكن نشر أسبوع {who} وحده: أول جدول منشور يجب أن يكون كاملاً. أنشر المسودة كلها؟")],
                'action': {'type': 'publish', 'what': 'teaching', 'run_id': run['id'], 'label': say(ar, 'Publish the whole draft', 'نشر المسودة كلها')}}
    have, mine = set(have), set(chosen)
    own = [s for s in view['sessions'] if mine & set(s.get('groups') or [])]
    if not own:
        return {'text': [say(ar, f"{who} has no sessions in this draft, so there is nothing of theirs to publish.", f"لا توجد محاضرات لـ {who} في هذه المسودة، لذلك لا يوجد ما يُنشر.")]}
    shared = [s for s in own if set(s.get('groups') or []) - mine]
    missing = [s for s in view['sessions'] if s['activity_id'] not in have and not mine & set(s.get('groups') or [])]
    text = [say(ar, f"Publish {who}'s week ({len(own)} sessions) from this draft into the published timetable? Everyone else keeps their published week, "
                    "and the combined week is checked for room, instructor and student clashes; it is published only if it passes.",
                f"نشر أسبوع {who} ({len(own)} محاضرة) من هذه المسودة داخل الجدول المنشور؟ يحتفظ الباقون بأسبوعهم المنشور، "
                "ويُفحص الأسبوع المدمج من تعارض القاعات والمحاضرين والطلاب؛ ويُنشر فقط إذا اجتاز الفحص.")]
    if shared:
        text.append(say(ar, f"{len(shared)} of them are lectures shared with other groups, so those groups get the new time for that lecture too.",
                        f"{len(shared)} منها محاضرات مشتركة مع مجموعات أخرى، لذلك تأخذ تلك المجموعات الوقت الجديد لها أيضاً."))
    if missing:
        text.append(say(ar, f"The published timetable doesn't have {len(missing)} other sessions that were added after it was published (new groups or courses). "
                            "They come along from this draft too; without them the published timetable would be incomplete and can't be published.",
                        f"الجدول المنشور لا يحتوي {len(missing)} محاضرة أخرى أضيفت بعد نشره (مجموعات أو مقررات جديدة). "
                        "تُضاف من هذه المسودة أيضاً؛ بدونها يكون الجدول المنشور ناقصاً ولا يمكن نشره."))
    return {'text': text, 'action': {'type': 'publish_merged', 'run_id': run['id'], 'groups': list(chosen),
                                     'label': say(ar, f'Publish {who}', f'نشر {who}')}}


def publishing(intent, slots, view, ar):
    """Publish or unpublish the timetable on screen (or the latest one), explaining what stands in the way first."""
    exams = slots.get('schedule_kind') == 'exams' if slots.get('schedule_kind') else slots.get('exams') or (view.get('screen') or {}).get('page') == 'exams'
    if exams:
        e = view['exam_run']
        if intent == 'unpublish':
            if not e or not e['published']:
                return {'text': [say(ar, 'This exam timetable is not published.', 'جدول الامتحانات هذا غير منشور.')]}
            return {'text': [say(ar, 'Unpublish this exam timetable? It will no longer appear in the portals.', 'إلغاء نشر جدول الامتحانات هذا؟ لن يظهر في البوابات.')],
                    'action': {'type': 'unpublish', 'what': 'exams', 'run_id': e['id'], 'label': say(ar, 'Unpublish', 'إلغاء النشر')}}
        problem = (not e and say(ar, 'There is no exam timetable yet.', 'لا يوجد جدول امتحانات بعد.')) or \
            (e['published'] and say(ar, 'The latest exam timetable is already published.', 'آخر جدول امتحانات منشور بالفعل.')) or \
            (e['status'] != 'completed' and say(ar, 'The latest exam timetable did not complete, so it cannot be published.', 'آخر جدول امتحانات لم يكتمل، لذلك لا يمكن نشره.')) or \
            (not e['halls'] and say(ar, 'It has dates and times only; publishing needs exam halls and invigilators. Create it again with halls on the Exams page.',
                                   'به تواريخ وأوقات فقط؛ النشر يحتاج قاعات ومراقبين. أنشئه مرة أخرى بالقاعات من صفحة الامتحانات.')) or \
            (e['stale'] and say(ar, 'The data changed since it was made. Create it again, then publish.', 'تغيرت البيانات بعد إنشائه. أنشئه مرة أخرى ثم انشره.'))
        if problem:
            return {'text': [problem]}
        return {'text': [say(ar, f"Publish this exam timetable ({e['kind']})? Students and instructors will see it, and it replaces the one published now.",
                             f"نشر جدول الامتحانات هذا ({e['kind']})؟ سيراه الطلاب والمحاضرون، ويحل محل المنشور حالياً.")],
                'action': {'type': 'publish', 'what': 'exams', 'run_id': e['id'], 'label': say(ar, 'Publish', 'نشر')}}
    run = view['run']
    meant = view.get('meant')
    if meant and intent == 'publish':
        if meant['status'] in ('queued', 'running'):
            what = meant.get('name') or say(ar, 'The timetable', 'الجدول')
            return {'text': [say(ar, f"{what} is still being generated, so it can't be published yet. Ask me again when it has finished; I'll publish that one.",
                                 f"{what} ما زال قيد الإنشاء، لذلك لا يمكن نشره بعد. اطلب مني مرة أخرى عندما ينتهي وسأنشره.")],
                    'action': {'type': 'open', 'page': 'timetable', 'run_id': meant['id'], 'label': say(ar, 'Watch it', 'متابعة')}}
        return {'text': [say(ar, f"That timetable did not finish with a valid result ({meant['status']}), so it can't be published. Shall I find what stopped it?",
                             f"ذلك الجدول لم ينتهِ بنتيجة صالحة ({meant['status']})، لذلك لا يمكن نشره. أبحث عن السبب؟")],
                'choices': [{'label': say(ar, 'Find and fix the problems', 'ابحث وأصلح'), 'text': 'fix the problems'}]}
    if run and not run.get('on_screen') and not run.get('talked_about') and view.get('newest'):
        run = {**run, **view['newest']}  # nothing on screen: the newest draft, not the published one
    if intent == 'unpublish':
        if not view.get('published_id'):
            return {'text': [say(ar, 'No teaching timetable is published right now.', 'لا يوجد جدول تدريس منشور الآن.')]}
        return {'text': [say(ar, 'Unpublish the teaching timetable? Students and instructors will no longer see it until another one is published.',
                             'إلغاء نشر جدول التدريس؟ لن يراه الطلاب والمحاضرون حتى يُنشر جدول آخر.')],
                'action': {'type': 'unpublish', 'what': 'teaching', 'run_id': view['published_id'], 'label': say(ar, 'Unpublish', 'إلغاء النشر')}}
    if not run:
        return {'text': [say(ar, 'There is no valid timetable to publish yet.', 'لا يوجد جدول صالح للنشر بعد.')]}
    if run['published']:
        return {'text': [say(ar, 'That timetable is already published.', 'هذا الجدول منشور بالفعل.')]}
    seen = view.get('screen') or {}
    chosen = list(slots.get('groups') or []) or ([seen['group']] if slots.get('one_group') and seen.get('group') else [])
    if intent == 'publish' and chosen:
        return publish_groups(chosen, run, view, ar)
    if not run['complete']:
        codes = {r['id']: r['data'].get('code') for r in view['records'] if r['kind'] == 'groups'}
        part = ', '.join(codes.get(s.get('group')) or (s['programme'] + (say(ar, ' year ', ' سنة ') + str(s['year']) if s.get('year') else '')) for s in run.get('scope') or [])
        if view.get('published_id') and not run['stale']:
            return {'text': [say(ar, f"This draft covers only {part}. I can publish it into the published timetable: its sessions replace {part}'s there, everyone else keeps their week, "
                                     "and the combined week is checked for room, instructor and student clashes. It is published only if it passes.",
                                 f"هذه المسودة تغطي {part} فقط. أستطيع نشرها داخل الجدول المنشور: تحل محاضراتها محل محاضرات {part} هناك، ويحتفظ الباقون بأسبوعهم، "
                                 "ويُفحص الأسبوع المدمج من تعارض القاعات والمحاضرين والطلاب. يُنشر فقط إذا اجتاز الفحص.")],
                    'action': {'type': 'publish_merged', 'run_id': run['id'], 'label': say(ar, 'Publish into the published timetable', 'نشر داخل الجدول المنشور'),
                               'again': f"generate a timetable for {part}"}}
        return {'text': [say(ar, f"This draft is only part of the timetable ({part}). Only a complete timetable can be published, so every student and instructor gets one consistent week.",
                             f"هذه المسودة جزء من الجدول فقط ({part}). يُنشر الجدول الكامل فقط، حتى يحصل كل طالب ومحاضر على أسبوع متسق."),
                         say(ar, 'Generate the whole university (or the remaining programmes on top of this draft on the Timetable page), then publish that.',
                             'أنشئ جدول الجامعة كلها (أو البرامج المتبقية فوق هذه المسودة من صفحة الجدول)، ثم انشره.')],
                'choices': [{'label': say(ar, 'Generate the whole university', 'إنشاء جدول الجامعة كلها'), 'text': 'generate the whole university timetable'}]}
    if run['stale']:
        return {'text': [say(ar, 'The data changed since this draft was made, so it may no longer be valid. Generate a new draft, then publish it.',
                             'تغيرت البيانات بعد إنشاء هذه المسودة، لذلك قد لا تكون صالحة. أنشئ مسودة جديدة ثم انشرها.')],
                'choices': [{'label': say(ar, 'Generate the whole university', 'إنشاء جدول الجامعة كلها'), 'text': 'generate the whole university timetable'}]}
    made = local_time(run.get('created_at'), view.get('timezone'))
    when = say(ar, f', made at {made}', f'، أُنشئت الساعة {made}') if made else ''
    which = say(ar, 'the timetable on your screen', 'الجدول المعروض أمامك') if run.get('on_screen') else \
        say(ar, f"the timetable we've been talking about{' (' + run['name'] + ')' if run.get('name') else ''}{when}",
            f"الجدول الذي نتحدث عنه{' (' + run['name'] + ')' if run.get('name') else ''}{when}") if run.get('talked_about') else \
        say(ar, f'the newest draft{when}', f'أحدث مسودة{when}')
    shown = filtered_view(view) if run.get('on_screen') else None
    if shown:
        # The page shows one group, year or programme; the draft is still the whole week.
        name, count = shown
        kept = run.get('kept') or 0
        made = say(ar, f" {run['sessions'] - kept} were planned in this draft and the other {kept} keep the times of the timetable it was built on.",
                   f" منها {run['sessions'] - kept} خُططت في هذه المسودة، والباقي ({kept}) يحتفظ بأوقات الجدول الذي بُنيت عليه.") if kept else ''
        return {'text': [say(ar, f"Your screen shows {name} ({count} sessions), but this draft is the whole university's timetable: {run['sessions']} sessions.{made}",
                             f"الشاشة تعرض {name} ({count} محاضرة)، لكن هذه المسودة جدول الجامعة كلها: {run['sessions']} محاضرة.{made}"),
                         say(ar, "Publishing it gives everyone this week, so it is checked again against the current data first and replaces the one published now. Publish it?",
                             "نشرها يعطي الجميع هذا الأسبوع، لذلك تُفحص مرة أخرى مقابل البيانات الحالية أولاً وتحل محل المنشور حالياً. هل أنشرها؟")],
                'action': {'type': 'publish', 'what': 'teaching', 'run_id': run['id'], 'label': say(ar, 'Publish', 'نشر')}}
    return {'text': [say(ar, f"Publish {which} ({run['sessions']} sessions)? It is checked again against the current data; students and instructors will then see it, and it replaces the one published now.",
                         f"نشر {which} ({run['sessions']} محاضرة)؟ سيُفحص مرة أخرى مقابل البيانات الحالية، ثم يراه الطلاب والمحاضرون ويحل محل المنشور حالياً.")],
            'action': {'type': 'publish', 'what': 'teaching', 'run_id': run['id'], 'label': say(ar, 'Publish', 'نشر')}}


def plan_parts(view, limit=340):  # parts of ~280–330 sessions each solved in about 4 minutes on the demo; ~440 did not
    """Parts for a whole timetable too large for one run, or None when one run can place it.

    Each programme stays in one part when it fits (split by year only when it doesn't); parts hold up to
    `limit` sessions, below the solver's limit, so shared lectures counted elsewhere still fit."""
    from app.solver import MAX_SESSIONS
    records = {r['id']: r['data'] for r in view['records']}
    courses = [r['data'] for r in view['records'] if r['kind'] == 'courses']
    if sum(c.get('sessions', 1) for c in courses) <= MAX_SESSIONS:
        return None
    units = {}
    for c in courses:
        cohorts = sorted({(records.get(g, {}).get('major') or '', records.get(g, {}).get('year')) for g in c.get('group_ids', [])}, key=lambda x: (x[0], x[1] or 0))
        if cohorts:
            units[cohorts[0]] = units.get(cohorts[0], 0) + c.get('sessions', 1)
    by_programme = {}
    for (major, year), n in units.items():
        by_programme.setdefault(major, {})[year] = n
    items = []
    for major in sorted(by_programme, key=lambda m: -sum(by_programme[m].values())):
        years = by_programme[major]
        if sum(years.values()) <= limit:
            items.append(([{'programme': major, 'year': None}], sum(years.values())))
        else:
            items += [([{'programme': major, 'year': y}], n) for y, n in sorted(years.items(), key=lambda x: x[0] or 0)]
    parts, sizes = [], []
    for scope, n in items:  # largest first, each into the first part with room
        for i, size in enumerate(sizes):
            if size + n <= limit:
                parts[i] += scope; sizes[i] += n
                break
        else:
            parts.append(list(scope)); sizes.append(n)
    return parts


def answer(meaning, view, ar):
    """{'text': [...lines], 'action': {...} | None, 'needs': str | None}."""
    intent, slots = meaning['intent'], meaning['slots']
    run = view['run']
    if intent == 'cancel':
        return {'text': [say(ar, 'OK, cancelled. What else can I do?', 'تمام، تم الإلغاء. أقدر أساعد في إيه تاني؟')], 'forget': True}
    if intent == 'create_course':
        from app.assistant_courses import step as course_step
        ar = slots.setdefault('ar', ar)
        result = course_step(slots, view, lambda en, a: a if ar else en)
        if 'form' in result:
            slots['form'] = result['form']
        slots['field'] = result.get('field')
        slots.pop('unreadable', None)
        return result
    if intent == 'improve_schedule':
        from app.assistant_improve import improve
        return improve(slots, view, lambda en, a: a if ar else en)
    if intent == 'split_group':
        from app.assistant_fixes import split_group
        return split_group(slots['group'], view, lambda en, a: a if ar else en) or {'text': [say(ar, 'Which group?', 'أي مجموعة؟')]}
    if intent == 'fix_problems':
        from app.assistant_fixes import diagnose, reply as fix_reply
        found = diagnose(view, view.get('checks') or {}, None, lambda en, a: a if ar else en)
        return fix_reply(found, lambda en, a: a if ar else en) or {'text': [say(ar, 'Nothing blocks generation right now.', 'لا شيء يمنع الإنشاء الآن.')],
                                                                    'choices': [{'label': say(ar, 'Generate the whole university', 'إنشاء جدول الجامعة كلها'), 'text': 'generate the whole university timetable'}]}
    if intent == 'course_add':
        from app.assistant_courses import add_to_course
        return add_to_course(normalise(slots['raw']), slots['raw'], view, lambda en, a: a if ar else en) or \
            {'text': [say(ar, "Which course? I couldn't find it by that name or code.", 'أي مقرر؟ لم أجده بهذا الاسم أو الكود.')]}
    if intent in TASKS:
        ar = slots.setdefault('ar', ar) if intent == 'create_account' else ar
        step = answer_task(meaning, view, ar, say)
        if step and intent == 'create_account':
            if 'form' in step:
                slots['form'] = step['form']
            slots['field'] = step.get('field')
            if slots.pop('unreadable', None) and step.get('asking'):
                step['text'] = [say(ar, "Sorry, I couldn't read that.", 'عذراً، لم أفهم الإجابة.')] + step['text']
        return step or {'text': [say(ar, "I didn't understand that.", 'لم أفهم ذلك.')], 'unknown': True}
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
        which = ('the timetable on your screen', 'الجدول المعروض أمامك') if run.get('on_screen') else \
            ('the timetable we generated in this chat', 'الجدول الذي أنشأناه في هذه المحادثة') if run.get('talked_about') else \
            ('the published timetable', 'الجدول المنشور') if run['published'] else ('the latest valid timetable', 'الجدول الأحدث الصالح')
        source = say(ar, f"From {which[0]}{' (inputs changed since)' if run['stale'] else ''}.", f"من {which[1]}{' (تغيرت المدخلات بعده)' if run['stale'] else ''}.")
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
        if scope:
            # A group (often one just added) that no course lists has nothing to schedule yet.
            members = {g['id'] for g in view['records'] if g['kind'] == 'groups' and any(
                g['data'].get('major') == s['programme'] and s.get('year') in (None, g['data'].get('year')) and s.get('group') in (None, g['id']) for s in scope)}
            taught = {gid for r in view['records'] if r['kind'] == 'courses' for gid in r['data'].get('group_ids', [])}
            if members and not members & taught:
                codes = ', '.join(sorted(g['data'].get('code') for g in view['records'] if g['id'] in members)[:5])
                from app.assistant_courses import join_course, sibling_courses
                # Offer what the rest of its programme and year take, so it can be scheduled right after.
                offer = sibling_courses(next(iter(members)), view) if len(members) == 1 else []
                if offer:
                    gid = next(iter(members))
                    items = []
                    for course in offer:
                        catalog, updates, creates = join_course(course, [gid], view)
                        items.append({'course_id': course['id'], 'catalog': catalog, 'updates': updates, 'creates': creates})
                    g = next(r['data'] for r in view['records'] if r['id'] == gid)
                    listed = ', '.join(f"{c['name']} ({c['code']})" for c in offer[:8]) + (say(ar, f' and {len(offer) - 8} more', f' و{len(offer) - 8} أخرى') if len(offer) > 8 else '')
                    return {'text': [say(ar, f"{codes} is not in any course yet, so there is nothing to schedule for it.", f"{codes} غير مضافة لأي مقرر بعد، لذلك لا يوجد ما يُجدول لها."),
                                     say(ar, f"The other {g.get('major')} year {g.get('year')} groups take {len(offer)} courses: {listed}.",
                                         f"باقي مجموعات {g.get('major')} سنة {g.get('year')} يدرسون {len(offer)} مقررات: {listed}."),
                                     say(ar, f"Add {codes} to all of them? It joins their lectures and gets its own tutorials and labs; then I can generate its timetable.",
                                         f"إضافة {codes} إليها كلها؟ تنضم لمحاضراتها وتحصل على سكاشن ومعامل خاصة؛ ثم أنشئ جدولها.")],
                            'action': {'type': 'update_courses', 'items': items, 'group_code': codes, 'label': say(ar, f'Add to these {len(offer)} courses', f'إضافة إلى {len(offer)} مقررات')},
                            'choices': [{'label': say(ar, 'Choose courses myself', 'أختار المقررات بنفسي'), 'text': 'open course setup'}]}
                return {'text': [say(ar, f"{codes} is not in any course yet, so there is nothing to schedule for it. Add it to its courses (for example \"add {codes} to Network Security\"), or in Course setup.",
                                     f"{codes} غير مضافة لأي مقرر بعد، لذلك لا يوجد ما يُجدول لها. أضفها لمقرراتها (مثلاً \"أضف {codes} إلى Network Security\") أو من إعداد المقررات.")],
                        'action': {'type': 'open', 'page': 'courses', 'label': say(ar, 'Open Course setup', 'فتح إعداد المقررات')}}
        codes = {r['id']: r['data'].get('code') or r['data'].get('name') for r in view['records'] if r['kind'] == 'groups'}
        named = [codes[s['group']] if s.get('group') else s['programme'] + (say(ar, ' year ', ' سنة ') + str(s['year']) if s['year'] else '') for s in scope or []]
        what = say(ar, 'the whole university', 'الجامعة كلها') if scope is None else ', '.join(named)
        last = view['last_status']
        if last and last['status'] in ('queued', 'running'):
            return {'text': [say(ar, 'A timetable is already being generated. Wait for it to finish first.', 'يوجد جدول قيد الإنشاء الآن. انتظر حتى ينتهي.')],
                    'action': {'type': 'open', 'page': 'timetable', 'label': say(ar, 'Watch it', 'متابعة')}}
        shared = say(ar, ' Lectures it shares with other groups are placed for those groups too.', ' المحاضرات المشتركة مع مجموعات أخرى تُجدول لهم أيضاً.') if scope and any(s.get('group') for s in scope) else ''
        inside = view.get('published_id') if scope else None
        if inside:
            shared += say(ar, ' It is planned inside the published timetable: everyone else keeps their sessions, and anything added since it was published is placed too, so the result can be published directly.',
                          ' يُخطط داخل الجدول المنشور: يحتفظ الجميع بمحاضراتهم، ويُجدول ما أضيف بعد النشر أيضاً، لذلك يمكن نشر النتيجة مباشرة.')
        parts = plan_parts(view) if scope is None else None
        if parts:
            # Too big for one run: build it in parts, each placed around the ones before (the server chains them).
            total = sum(r['data'].get('sessions', 1) for r in view['records'] if r['kind'] == 'courses')
            label = lambda part: ', '.join(f"{u['programme']}" + (say(ar, f" year {u['year']}", f" سنة {u['year']}") if u.get('year') else '') for u in part)
            generate = {'type': 'generate', 'scope': parts[0], 'then': parts[1:], 'settings': {'time_limit_seconds': 240, 'search_workers': 4},
                        'label': say(ar, f'Generate in {len(parts)} parts', f'إنشاء على {len(parts)} أجزاء'), 'version': view['version']}
            text = [say(ar, f"The whole university is {total} sessions, more than one run can place ({MAX_SESSIONS}), so I'll build it in {len(parts)} parts, each placed around the ones before:",
                        f"الجامعة كلها {total} حصة، أكثر مما يستطيع تشغيل واحد ({MAX_SESSIONS})، لذلك سأنشئها على {len(parts)} أجزاء، كل جزء حول ما قبله:")]
            text += [f"{n}. {label(part)}" for n, part in enumerate(parts, 1)]
            text.append(say(ar, f"Each part gets up to 4 minutes, so about {len(parts) * 4 + 2} minutes in all. They start one after another on their own; the last part is the complete timetable. Nothing is published.",
                            f"كل جزء حتى 4 دقائق، أي حوالي {len(parts) * 4 + 2} دقيقة. تبدأ تلقائياً واحداً بعد الآخر؛ الجزء الأخير هو الجدول الكامل. لا يُنشر شيء."))
            if view.get('checks'):
                from app.assistant_fixes import diagnose, reply as fix_reply
                found = diagnose(view, view['checks'], None, lambda en, a: a if ar else en)
                if found['count']:
                    return fix_reply(found, lambda en, a: a if ar else en, then=generate if found['steps'] else None,
                                     intro=say(ar, f"Before generating: {found['count']} session(s) couldn't be scheduled as things are.", f"قبل الإنشاء: {found['count']} حصة لا يمكن جدولتها."))
            return {'text': text, 'action': generate}
        generate = {'type': 'generate', 'scope': scope, 'label': say(ar, 'Generate', 'إنشاء'), 'version': view['version'],
                    **({'base_run_id': inside, 'replace': True} if inside else {}),
                    **({'filter': {'group': scope[0]['group']}} if scope and len(scope) == 1 and scope[0].get('group') else
                       {'filter': {'major': scope[0]['programme'], 'year': str(scope[0]['year']) if scope[0]['year'] else ''}} if scope and len(scope) == 1 else {})}
        if view.get('checks'):
            # Check first: what would stop this generation, and what can be fixed before it starts.
            from app.assistant_fixes import diagnose, reply as fix_reply
            in_scope = None if scope is None else [g['id'] for g in view['records'] if g['kind'] == 'groups' and any(
                g['data'].get('major') == s['programme'] and s.get('year') in (None, g['data'].get('year')) and s.get('group') in (None, g['id']) for s in scope)]
            found = diagnose(view, view['checks'], in_scope, lambda en, a: a if ar else en)
            if found['count']:
                return fix_reply(found, lambda en, a: a if ar else en, then=generate if found['steps'] else None,
                                 intro=say(ar, f"Before generating {what}: {found['count']} session(s) couldn't be scheduled as things are.",
                                           f"قبل إنشاء {what}: {found['count']} حصة لا يمكن جدولتها بالوضع الحالي."))
        return {'text': [say(ar, f'I will generate a draft timetable for {what}{" only" if scope else ""}. It runs on the solver and appears on the Timetable page; nothing is published.',
                             f'سأنشئ مسودة جدول لـ {what}{" فقط" if scope else ""}. تعمل على المحلل وتظهر في صفحة الجدول؛ لا يُنشر شيء.') + shared],
                'action': generate}
    if intent == 'exam_timetable':
        kind = slots.get('exam_kind') or 'midterm'
        dates = slots.get('dates') or []
        if slots.get('scope_query') and not (slots.get('programmes') or slots.get('groups') or slots.get('courses')):
            return {'text': [say(ar, f"Which programme or group do you mean by '{slots['scope_query']}'? Please choose an existing name.", f"أي برنامج أو مجموعة تقصد بـ '{slots['scope_query']}'؟ اختر اسماً موجوداً.")],
                    'choices': [{'label': name, 'text': name} for name in programmes(view['records'])], 'asking': True}
        if len(dates) < 2:
            return {'text': [say(ar, f'Which dates should the {kind} timetable cover? For example "from 20 Dec to 31 Dec".',
                                 'ما هي تواريخ فترة الامتحانات؟ مثلاً "من 20 ديسمبر إلى 31 ديسمبر".')], 'asking': True}
        body = {'kind': kind, 'start_date': dates[0], 'end_date': dates[1]}
        scope_label = say(ar, 'all courses with that exam', 'كل المقررات التي لها هذا الامتحان')
        if slots.get('programmes') or slots.get('year') or slots.get('groups') or slots.get('courses'):
            target_groups = {record['id'] for record in view['records'] if record['kind'] == 'groups'
                and (not slots.get('programmes') or record['data'].get('major') in slots['programmes'])
                and (not slots.get('year') or record['data'].get('year') == slots['year'])
                and (not slots.get('groups') or record['id'] in slots['groups'])}
            named_activities = [record for record in view['records'] if record['id'] in (slots.get('courses') or [])]
            named_catalogue = {record['data'].get('course_id') for record in named_activities}
            selected = [course['id'] for course in view.get('catalog', [])
                if (course['id'] in named_catalogue if slots.get('courses') else bool(target_groups & set(course.get('group_ids') or [])))]
            if not selected:
                return {'text':[say(ar, 'I could not find catalogue courses for that exam scope. Which programme, year, group or course should I use?', 'لم أجد مقررات لهذا النطاق. أي برنامج أو سنة أو مجموعة أو مقرر تقصد؟')], 'asking':True}
            body['course_ids'] = sorted(set(selected))
            scope_label = ', '.join(slots.get('programmes') or []) or ', '.join(record['data'].get('code', record['id']) for record in view['records'] if record['id'] in (slots.get('groups') or slots.get('courses') or [])) or say(ar, 'the selected cohort', 'المجموعة المختارة')
            if slots.get('year'):
                scope_label += say(ar, f" year {slots['year']}", f" سنة {slots['year']}")
            scope_label += say(ar, f' ({len(selected)} courses; shared courses include all their students)', f' ({len(selected)} مقرر؛ المقررات المشتركة تشمل كل طلابها)')
        for option in ('exclude_fridays', 'use_halls', 'assign_invigilators', 'max_exams_per_cohort_day'):
            if option in slots and (slots[option] is False or option == 'max_exams_per_cohort_day'):
                body[option] = slots[option]
        if kind == 'final':
            body['skip'] = [] if slots.get('include_makeups') else [f'{c}:makeup' for c in view['second_chance']]  # as on the Exams page: second chances start unticked
        if kind == 'quiz':
            body.update(quiz_number=slots.get('quiz_number') or 1, quiz_minutes=min(60, max(15, round((slots.get('quiz_minutes') or 30) / 15) * 15)))
        title = {'final': say(ar, 'finals' + (' (with second-chance midterms in the first slot)' if slots.get('include_makeups') else ''), 'النهائي' + (' (والفرصة الثانية في أول فترة)' if slots.get('include_makeups') else '')),
                 'midterm': say(ar, 'midterms', 'منتصف الفصل'),
                 'quiz': say(ar, f"quiz {body.get('quiz_number')} ({body.get('quiz_minutes')} min)", f"الاختبار القصير {body.get('quiz_number')} ({body.get('quiz_minutes')} دقيقة)")}[kind]
        friday_label = say(ar, 'Fridays off', 'بدون أيام الجمعة') if body.get('exclude_fridays', True) else say(ar, 'including Fridays', 'شامل أيام الجمعة')
        return {'text': [say(ar, f'I will create a draft exam timetable for the {title}, {dates[0]} to {dates[1]}, {friday_label}, {scope_label}.',
                             f'سأنشئ مسودة جدول امتحانات {title} من {dates[0]} إلى {dates[1]}، {friday_label}، {scope_label}.'),
                         say(ar, 'Second-chance midterms are left out. Ask me to include them if needed.', 'الفرص الثانية غير مضمنة؛ أضفها من صفحة الامتحانات.') if kind == 'final' and not slots.get('include_makeups') else ''],
                'action': {'type': 'exam', 'scope_verified': True, 'body': body, 'label': say(ar, 'Create exam timetable', 'إنشاء جدول الامتحانات'), 'version': view['version']}}
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
        seen = view.get('screen') or {}
        if not params and run.get('on_screen'):
            # Nothing named: the timetable as shown, with the page's group / year / programme filter.
            params = {k: v for k, v in (('group', seen.get('group')), ('year', seen.get('year')), ('major', seen.get('major'))) if v}
            if params.get('group'):
                params = {'group': params['group']}
        from urllib.parse import urlencode
        label = (by_id(view).get(params['group'], {}).get('data', {}).get('code') if 'group' in params else ' '.join(x for x in (params.get('major'), f"year {params['year']}" if params.get('year') else '') if x)) or say(ar, 'the whole timetable', 'الجدول كله')
        return {'text': [say(ar, f'Here is the PDF for {label}.', f'هذا ملف PDF لـ {label}.'), source],
                'action': {'type': 'download', 'url': f"/api/schedules/{run['id']}/timetable.pdf" + ('?' + urlencode(params) if params else ''), 'label': say(ar, 'Download PDF', 'تحميل PDF')}}
    if intent in ('publish', 'unpublish'):
        return publishing(intent, slots, view, ar)
    if intent == 'status':
        last = view['last_status']
        if not last:
            return {'text': [say(ar, 'No timetable has been generated yet.', 'لم يُنشأ أي جدول بعد.')]}
        chain = last.get('chain')
        if chain and last.get('chain_stopped'):
            why = {'stale_schedule': say(ar, 'the data changed while it was being built (records were added or edited), so the next part could not be placed around the earlier ones',
                                         'تغيرت البيانات أثناء الإنشاء (أُضيفت سجلات أو عُدلت)، فلم يمكن وضع الجزء التالي حول الأجزاء السابقة'),
                   'part_failed': say(ar, 'this part did not finish with a valid timetable', 'هذا الجزء لم ينتهِ بجدول صالح')}.get(last['chain_stopped'], last['chain_stopped'])
            return {'text': [say(ar, f"The whole-university build stopped after part {chain.get('step', 1)} of {chain.get('steps', '?')}: {why}.",
                                 f"توقف إنشاء جدول الجامعة بعد الجزء {chain.get('step', 1)} من {chain.get('steps', '?')}: {why}."),
                             say(ar, 'Build it again from the start? It uses the current data.', 'أنشئه من جديد؟ سيستخدم البيانات الحالية.')],
                    'choices': [{'label': say(ar, 'Build it again', 'أنشئه من جديد'), 'text': 'generate the whole university timetable'}]}
        if chain and last['status'] in ('queued', 'running'):
            return {'text': [say(ar, f"Building the whole university: part {chain.get('step', 1)} of {chain.get('steps', '?')} is {last['status']}. The next parts start on their own.",
                                 f"جارٍ إنشاء جدول الجامعة: الجزء {chain.get('step', 1)} من {chain.get('steps', '?')} {'في الانتظار' if last['status'] == 'queued' else 'قيد التشغيل'}. الأجزاء التالية تبدأ تلقائياً.")],
                    'action': {'type': 'open', 'page': 'timetable', 'label': say(ar, 'Watch it', 'متابعة')}}
        if last['status'] in ('blocked', 'failed', 'infeasible', 'timeout'):
            return {'text': [say(ar, f"The latest run stopped ({last['status']}). Shall I find what stopped it and fix it?", f"آخر تشغيل توقف ({last['status']}). أبحث عن السبب وأصلحه؟")],
                    'choices': [{'label': say(ar, 'Find and fix the problems', 'ابحث وأصلح'), 'text': 'fix the problems'}]}
        lines = [say(ar, f"Latest run: {last['status']}, {last['sessions']} sessions, validation {'passed' if last['passed'] else 'not passed' if last['passed'] is False else 'pending'}.",
                     f"آخر تشغيل: {last['status']}، {last['sessions']} محاضرة، التحقق {'ناجح' if last['passed'] else 'غير ناجح' if last['passed'] is False else 'قيد الانتظار'}.")]
        if run:
            lines.append(say(ar, f"Timetable in use: {'published' if run['published'] else 'not published'}, {run['sessions']} sessions{', inputs changed since' if run['stale'] else ''}.",
                             f"الجدول المستخدم: {'منشور' if run['published'] else 'غير منشور'}، {run['sessions']} محاضرة{'، تغيرت المدخلات بعده' if run['stale'] else ''}."))
        if view['exam_run']:
            lines.append(say(ar, f"Latest exam timetable: {view['exam_run']['kind']}, {view['exam_run']['status']}.", f"آخر جدول امتحانات: {view['exam_run']['kind']}، {view['exam_run']['status']}."))
        return {'text': lines, 'action': {'type': 'open', 'page': 'timetable', 'label': say(ar, 'Open Timetable', 'فتح الجدول')}}
    return {'text': [say(ar, "I didn't understand that.", 'لم أفهم ذلك.')], 'unknown': True}


CAN_EN = ['Is room A3.128 free on Sunday at 10:00?', 'Generate a timetable', "Dr. Ahmed can't teach Sunday before 10:30", 'Move Math I of INF1-G7 to Monday 10:15',
          'Change room A3.128 capacity to 70', 'Add a new instructor', 'Create a student account', 'Publish it', 'Create an exam timetable', 'Statistics report',
          'Can I generate?', 'Open Semester settings']
CAN_AR = ['هل قاعة A3.128 فاضية يوم الأحد الساعة 10؟', 'اعمل جدول', 'د. أحمد مش متاح الأحد قبل 10:30', 'أضف محاضر جديد', 'اعمل حساب طالب',
          'انشره', 'اعمل جدول امتحانات', 'تقرير', 'افتح الإعدادات']
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
                'required': ['command', 'intent', 'record_kind', 'room', 'instructor', 'group', 'programme', 'year', 'course', 'days', 'start_time', 'end_time', 'exam_kind', 'start_date', 'end_date', 'whole_university'],
                'properties': {'command': {'type': 'string', 'maxLength': 300},
                               'intent': {'type': 'string', 'enum': [*INTENTS, 'unknown']},
                               'record_kind': {'type': ['string', 'null'], 'enum': ['instructors', 'rooms', 'groups', 'courses', None]},
                               'room': {'type': ['string', 'null']}, 'instructor': {'type': ['string', 'null']}, 'group': {'type': ['string', 'null']},
                               'programme': {'type': ['string', 'null']}, 'year': {'type': ['integer', 'null']}, 'course': {'type': ['string', 'null']},
                               'days': {'type': 'array', 'items': {'type': 'string', 'enum': ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']}},
                               'start_time': {'type': ['string', 'null']}, 'end_time': {'type': ['string', 'null']},
                               'exam_kind': {'type': ['string', 'null'], 'enum': ['quiz', 'midterm', 'final', None]},
                               'start_date': {'type': ['string', 'null']}, 'end_date': {'type': ['string', 'null']}, 'whole_university': {'type': 'boolean'}}}
MODEL_PROMPT = """You route messages from a university timetabling administrator (English, Arabic or Egyptian Arabic) to one intent of a scheduling website. Reply only with the JSON object.
Intents: room_schedule (a room's sessions or whether it is free), free_rooms (which rooms are free at a time), instructor_schedule, group_schedule (a student group), course_schedule (when a course meets), generate_timetable (create a teaching timetable for a programme/year or the whole university), exam_timetable (create quiz/midterm/final exam timetable), download_pdf, status (latest generation run), create_record (add a new instructor, room, student group or course; set record_kind), help, unknown.
First write "command": the request rewritten as exactly ONE short plain-English command in the style of these examples, keeping names, codes, days and times exactly. Never join two commands and never add anything the message did not ask for (empty string if it is not a request to the website):
{commands}
Then fill the other fields. Copy names and codes exactly as the message writes them; translate Arabic day names to English; times as HH:MM 24-hour; dates as YYYY-MM-DD (the current year is {year}). Use null when the message does not say. Programmes known: {programmes}."""


COMMANDS = ['Is room A3.128 free on Sunday at 10:00?', 'Free labs on Monday 11:30 for 30 students', "Dr. Ahmed Hassan's schedule on Tuesday",
            'What does BA5-G7 have on Wednesday?', 'When is Math I?', 'Generate the timetable for Business Administration year 3', 'Generate the whole university timetable',
            'Create the finals timetable from 20 Dec to 31 Dec', 'Download the PDF for BA5-G7', 'Status of the latest run', 'Publish it', 'Unpublish the timetable',
            'Add a new instructor', 'Add room C7.201 with 40 seats', 'Add a student group', "Dr. Ahmed Hassan can't teach on Sunday before 10:30",
            'Show the rules for Dr. Ahmed Hassan', 'Remove the rule for room A3.128', 'Approve the draft rules', 'Change room A3.128 capacity to 70',
            'Set Dr. Ahmed Hassan day off to Thursday', 'Change BA5-G7 size to 30', 'Delete room C7.201', 'Delete instructor Dr. Ahmed Hassan', 'Create a student account', 'Reset password for name@example.com',
            'Move Management Accounting of BA5-G7 from Wednesday 8:30 to Monday 10:15', 'Lock Management Accounting of BA5-G7 on Wednesday', 'Rename this draft to Plan B',
            'Stop the generation', 'Statistics report', 'Export csv', 'Can I generate?', 'When is the Math I final?', 'Exam timetable pdf', 'Open the accounts page',
            'Open semester settings', 'Import data from an excel file']


def model_settings():
    if os.environ.get('JADWAI_AI_ENABLED', '').lower() != 'true' or os.environ.get('JADWAI_AI_PROVIDER', '').lower() != 'local':
        return None
    from app.local_provider import DEFAULT_MODEL, DEFAULT_URL
    return os.environ.get('JADWAI_LOCAL_MODEL', DEFAULT_MODEL), os.environ.get('JADWAI_LOCAL_URL', DEFAULT_URL).rstrip('/'), float(os.environ.get('JADWAI_LOCAL_TIMEOUT_SECONDS', '180'))


async def model_understand(raw, view, *, transport=None, history=()):
    """The local model maps the message to an intent with names as written; resolution stays here."""
    settings = model_settings()
    if not settings:
        return None
    model, url, timeout = settings
    payload = {'model': model, 'stream': False, 'format': MODEL_SCHEMA, 'keep_alive': '30m', 'options': {'temperature': 0, 'seed': 42, 'num_ctx': 4096},
               'messages': [{'role': 'system', 'content': MODEL_PROMPT.format(year=date.today().year, programmes='; '.join(programmes(view['records'])), commands='\n'.join('- ' + c for c in COMMANDS))},
                            *[{'role': h['role'], 'content': h['content']} for h in list(history)[-6:]],  # the chat so far, to resolve "it", "her", "that group"
                            {'role': 'user', 'content': raw}]}
    try:
        async with httpx.AsyncClient(transport=transport, timeout=timeout, trust_env=False, follow_redirects=False) as client:
            response = await client.post(url + '/api/chat', json=payload)
        data = json.loads(response.json()['message']['content']) if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(data, dict) or data.get('intent') not in (*INTENTS, 'unknown'):
        return None
    # The model's rewrite goes through the built-in understanding, so every command (and its checks) is reachable.
    command = data.get('command')
    if isinstance(command, str) and command.strip() and normalise(command) != normalise(raw):
        # One command only: of "X and Y", keep the part that is the kind of request the model itself chose.
        for part in [command] + re.split(r'\s+(?:and|then|also|و)\s+', command):
            part = part.strip(' .,')[:300]
            rewritten = understand(part, view, None) if part else {'intent': 'unknown'}
            if rewritten['intent'] != 'unknown' and (data['intent'] == 'unknown' or rewritten['intent'] == data['intent']) \
                    and (part != command or not re.search(r'\s(?:and|then)\s', command)):
                return {**rewritten, 'rewritten': part}
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


def extra(db, view, intent):
    """The heavier facts some answers need: the statistics report, or the input checks."""
    if intent == 'statistics' and view.get('run'):
        from app.statistics import build_statistics
        row = db.get(ScheduleRun, view['run']['id'])
        seen = view.get('screen') or {}
        scope = ({'group': seen['group']} if seen.get('group') else {k: seen[k] for k in ('year', 'major') if seen.get(k)}) if view['run'].get('on_screen') else None
        view['stats'] = build_statistics(row.snapshot, row.result, scope or None)
    if intent == 'move_session' and view.get('run'):
        row = db.get(ScheduleRun, view['run']['id'])
        view['run_rows'] = {'snapshot': row.snapshot, 'assignments': row.result['assignments']}  # to check a move as the server will
    if intent in ('input_checks', 'generate_timetable', 'fix_problems'):
        from app.preflight import inspect_inputs
        from app.schedules import snapshot_of
        view['checks'] = inspect_inputs(snapshot_of(db, db.get(Workspace, 1)))
    db.commit()


def chat_of(db, user, ident):
    chat = db.get(AssistantChat, ident) if ident else None
    if not chat or chat.user_id != user.id:
        fail(404, 'not_found')
    return chat


def message_data(m):
    return {'id': m.id, 'from': m.role, **m.body}


def history_of(db, chat, limit=12):
    """The chat's last messages as plain lines, for the local model."""
    rows = list(db.scalars(select(AssistantMessage).where(AssistantMessage.chat_id == chat.id).order_by(AssistantMessage.created_at.desc()).limit(limit)))
    return [{'role': 'user' if m.role == 'you' else 'assistant', 'content': ' '.join(m.body.get('text') if isinstance(m.body.get('text'), list) else [m.body.get('text') or ''])[:1800]}
            for m in reversed(rows) if not m.body.get('pending')]


@router.get('/chats')
def list_chats(user=Depends(administrator), db=Depends(db_session)):
    rows = db.scalars(select(AssistantChat).where(AssistantChat.user_id == user.id).order_by(AssistantChat.updated_at.desc()).limit(50))
    return [{'id': c.id, 'title': c.title, 'updated_at': c.updated_at} for c in rows]


@router.post('/chats', status_code=201)
def new_chat(user=Depends(administrator), db=Depends(db_session)):
    chat = AssistantChat(id=str(uuid4()), user_id=user.id, title='New chat', state={})
    db.add(chat); db.commit()
    return {'id': chat.id, 'title': chat.title, 'updated_at': chat.updated_at}


@router.get('/chats/{ident}')
def open_chat(ident: str, user=Depends(administrator), db=Depends(db_session)):
    chat = chat_of(db, user, ident)
    rows = db.scalars(select(AssistantMessage).where(AssistantMessage.chat_id == chat.id).order_by(AssistantMessage.created_at))
    return {'id': chat.id, 'title': chat.title, 'messages': [message_data(m) for m in rows]}


@router.delete('/chats/{ident}', status_code=204)
def delete_chat(ident: str, user=Depends(administrator), db=Depends(db_session)):
    db.delete(chat_of(db, user, ident)); db.commit()


class Done(Strict):
    note: list[str] = Field(default_factory=list, max_length=20)
    cancelled: bool = False
    confirmation_text: str | None = Field(default=None, max_length=200)
    result_context: list[dict] = Field(default_factory=list, max_length=12)
    # The record the action created or changed: the chat is now about it ("create a schedule for them").
    subject_kind: Literal['rooms', 'instructors', 'groups', 'courses', 'schedules', 'exam_schedules'] | None = None
    subject_id: str | None = Field(default=None, max_length=36)


@router.post('/chats/{ident}/messages/{message}/done')
def action_done(ident: str, message: str, body: Done, user=Depends(administrator), db=Depends(db_session)):
    """The admin confirmed a message's action; record it and what happened next."""
    chat = chat_of(db, user, ident)
    row = db.get(AssistantMessage, message)
    if not row or row.chat_id != chat.id or row.role != 'jai':
        fail(404, 'not_found')
    row.body = {**row.body, 'done': True, **({'cancelled': True} if body.cancelled else {})}
    note = None
    if body.confirmation_text:
        db.add(AssistantMessage(id=str(uuid4()), chat_id=chat.id, role='you', body={'text': body.confirmation_text}))
        db.flush()
    if body.note:
        note = AssistantMessage(id=str(uuid4()), chat_id=chat.id, role='jai', body={'text': [t[:1000] for t in body.note]})
        db.add(note)
    if body.subject_kind and body.subject_id and not body.cancelled:
        from app.assistant_context import remember_record
        state = dict(chat.state or {})
        memory = state.get('memory') or {}
        memory = {**memory, 'exam_run': body.subject_id} if body.subject_kind == 'exam_schedules' else {**memory, 'run': body.subject_id} if body.subject_kind == 'schedules' else remember_record(memory, body.subject_kind, body.subject_id)
        if body.subject_kind in ('schedules', 'exam_schedules'):
            memory['schedule_focus'] = {'kind': 'exams' if body.subject_kind == 'exam_schedules' else 'teaching', 'id': body.subject_id}
        chat.state = {**state, 'memory': memory}
    if body.result_context and len(json.dumps(body.result_context, default=str)) <= 20000:
        allowed = {'id', 'name', 'code', 'kind', 'role', 'email', 'active', 'version', 'group_id', 'instructor_id', 'advising_student_id', 'year', 'major', 'capacity', 'size', 'department', 'day_off', 'position'}
        recent = [{k: v for k, v in item.items() if k in allowed} for item in body.result_context]
        state = dict(chat.state or {})
        chat.state = {**state, 'memory': {**(state.get('memory') or {}), 'recent_results': recent}}
    chat.updated_at = utcnow(); db.commit()
    return {'note': message_data(note) if note else None}


def generated_in(db, chat, user):
    """The timetable a chat started generating, for chats from before it was remembered: the first run this admin
    started after the chat's latest confirmed "generate"."""
    for row in db.scalars(select(AssistantMessage).where(AssistantMessage.chat_id == chat.id, AssistantMessage.role == 'jai')
                          .order_by(AssistantMessage.created_at.desc()).limit(200)):
        if (row.body.get('action') or {}).get('type') == 'generate' and row.body.get('done') and not row.body.get('cancelled'):
            run = db.scalar(select(ScheduleRun).where(ScheduleRun.created_by == user.id, ScheduleRun.created_at >= row.created_at)
                            .order_by(ScheduleRun.created_at).limit(1))
            return run.id if run else None
    return None


@router.post('')
async def ask(body: Ask, user=Depends(administrator), db=Depends(db_session)):
    from app.assistant_context import remember, remember_record, resolve_references, with_context
    screen = body.screen.model_dump() if body.screen else {}
    chat = chat_of(db, user, body.chat_id) if body.chat_id else None
    # The timetable on screen, otherwise the one this chat is about ("publish it" from any page).
    talked = (((chat.state or {}).get('memory') or {}).get('run') or generated_in(db, chat, user)) if chat else None
    old_memory = ((chat.state or {}).get('memory') or {}) if chat else {}
    exam_id = (screen.get('run_id') if screen.get('page') == 'exams' else None) or old_memory.get('exam_run')
    teaching_id = screen.get('run_id') if screen.get('page') == 'timetable' else None
    view = view_of(db, teaching_id, talked, exam_id)
    view['screen'] = screen
    if chat is None and body.previous is None:
        chat = AssistantChat(id=str(uuid4()), user_id=user.id, title='New chat', state={})
        db.add(chat); db.flush()
    state = dict(chat.state or {}) if chat else {}
    previous = state.get('previous') if chat else body.previous
    memory = state.get('memory') or {}
    history = history_of(db, chat, limit=12) if chat and body.use_model else []
    chat_id = chat.id if chat else None
    db.commit()  # release the workspace lock before any model call; answers use the copy read above
    ar = bool(ARABIC.search(body.text))
    if not memory.get('schedule_focus') and chat:
        for saved in db.scalars(select(AssistantMessage).where(AssistantMessage.chat_id == chat.id, AssistantMessage.role == 'jai').order_by(AssistantMessage.created_at.desc()).limit(200)):
            action = saved.body.get('action') or {}
            if saved.body.get('done') and not saved.body.get('cancelled') and action.get('type') in ('exam', 'generate'):
                kind = 'exams' if action['type'] == 'exam' else 'teaching'
                ident = memory.get('exam_run' if kind == 'exams' else 'run')
                if ident: memory['schedule_focus'] = {'kind': kind, 'id': ident}
                break
    if screen.get('run_id') and screen.get('page') in ('exams', 'timetable'):
        memory['schedule_focus'] = {'kind': 'exams' if screen['page'] == 'exams' else 'teaching', 'id': screen['run_id']}
        if screen['page'] == 'exams': memory['exam_run'] = screen['run_id']
    view['memory'] = memory
    # "them", "it", "the group I just created": the record this chat is about, so every command understands it.
    filling = (previous or {}).get('asking') and (previous or {}).get('intent') in ('create_record', 'create_account') and \
        ((previous or {}).get('slots') or {}).get('field') in ('name', 'email', 'department', 'code')
    text = body.text if filling else resolve_references(body.text, memory, view)[0]
    meaning = with_context(normalise(text).translate(ARABIC_DIGITS), understand(text, view, previous), memory)
    source = 'built-in'
    settings = model_settings()
    discussion = bool(re.search(r'\b(explain how|explain the|before changing|do not change|don.t change|discuss|trade.?off)\b|اشرح|وضح', body.text.lower()))
    ordinal_followup = memory.get('recent_results') and re.search(r'\b(first|second|third|last|one above)\b|الأول|الثاني|التاني|التالت|الأخير', body.text.lower())
    if (discussion or ordinal_followup) and settings:
        meaning = {'intent': 'unknown', 'slots': {}, 'ambiguous': []}
    unsure = meaning['intent'] == 'unknown' or meaning.get('weak') or bool(state.get('capability_pending'))
    if (unsure or state.get('capability_pending')) and body.use_model and settings:
        from app.assistant_capabilities import converse as local_converse
        from app.main import app
        conversation = await local_converse(body.text, view, history, settings, app, pending=state.get('capability_pending'))
        if conversation:
            meaning = {'intent': 'conversation', 'slots': {}, 'ambiguous': [], 'held': conversation}
            source = conversation.get('source', 'local-model')
    elif unsure and state.get('capability_pending') and settings:
        meaning = {'intent': 'unknown', 'slots': {}, 'ambiguous': []}
    elif meaning.get('weak') and settings:
        # A guess from a name alone: let the local model read the whole sentence first.
        return_early = {'text': [say(ar, f'Let me check that with the local model ({settings[0]})…', f'دعني أتأكد من ذلك مع النموذج المحلي ({settings[0]})…')],
                        'retry_with_model': True}
        meaning = {'intent': 'unknown', 'slots': {}, 'ambiguous': [], 'held': return_early}
    if meaning['intent'] in ('statistics', 'input_checks', 'generate_timetable', 'fix_problems', 'move_session'):
        extra(db, view, meaning['intent'])
    reply = meaning['held'] if meaning.get('held') else answer(meaning, view, ar)
    if meaning['intent'] == 'add_rule' and settings:
        if not body.use_model:
            reply = {'text': [say(ar, 'I will interpret that with the local model before proposing any change.', 'سأفسر الطلب بالنموذج المحلي قبل اقتراح أي تعديل.')], 'retry_with_model': True}
        else:
            from app.local_provider import LocalProvider
            from app.extraction import ExtractionRequest, extract_candidate
            from app.openai_provider import PROMPT_VERSION
            from app.proposal_validation import validate_proposal
            from app.assistant_tasks import rule_line
            raw = meaning['slots'].get('raw') or body.text
            ctx = {'records': view['records'], 'calendar': view['calendar']}
            req = ExtractionRequest.create(raw, ctx, view['version'], PROMPT_VERSION, 'proposal-contract-v1')
            try:
                provider = LocalProvider.configured()
                result = await extract_candidate(provider, req, timeout_seconds=provider.timeout_seconds + 5, retry_limit=0)
                output = json.loads(result.candidate_json) if result.status == 'candidate' else None
                check = validate_proposal(output, records={r['id']: r['kind'] for r in view['records']}, calendar=view['calendar']) if output else None
                if check and check.valid and check.eligible_for_review:
                    rules = [p['data'] for p in output['proposals']]
                    reply = {'text': [say(ar, 'I understood this as:', 'فهمت الطلب كالتالي:')] + ['• ' + rule_line(rule, view, lambda en, a: a if ar else en) for rule in rules] +
                                    [say(ar, 'Add and approve these rules? Nothing changes until you confirm.', 'إضافة واعتماد هذه القيود؟ لن يتغير شيء حتى تؤكد.')],
                             'action': {'type': 'add_rules', 'text': raw, 'rules': rules, 'count': len(rules), 'version': view['version'], 'label': say(ar, 'Add and approve', 'إضافة واعتماد')}}
                else:
                    questions = (output or {}).get('clarifications') or (output or {}).get('unsupported') or []
                    reply = {'text': [say(ar, 'The local interpreter did not complete. Please retry; no rule was added.', 'لم يكمل المفسر المحلي الطلب. حاول مرة أخرى؛ لم تتم إضافة قيد.')]} if result.status != 'candidate' else {'text': [say(ar, 'I need clarification before creating a rule.', 'أحتاج توضيحًا قبل إنشاء القيد.')] + questions, 'asking': True}
                source = 'local-model'
            except (ValueError, TimeoutError):
                reply = {'text': [say(ar, 'The local interpreter did not complete. Please retry; no rule was added.', 'لم يكمل المفسر المحلي الطلب. حاول مرة أخرى؛ لم تتم إضافة قيد.')]}
    if source == 'local-model' and meaning.get('rewritten') and not reply.get('unknown'):
        reply['text'] = [say(ar, f'I understood this as: “{meaning["rewritten"]}”', f'فهمت طلبك هكذا: “{meaning["rewritten"]}”')] + reply['text']
    if reply.get('unknown'):
        if settings and not body.use_model:
            reply['text'].append(say(ar, f'Asking the local model ({settings[0]})…', f'جارٍ سؤال النموذج المحلي ({settings[0]})…'))
            reply['retry_with_model'] = True
        else:
            reply['text'] = [say(ar, "I can't do that yet, or I didn't understand it. Here is what I can do; pick one or rephrase:",
                                 'لا أستطيع ذلك بعد، أو لم أفهمه. هذا ما أقدر عليه؛ اختر أو أعد الصياغة:')]
            reply['choices'] = [{'label': x, 'text': x} for x in (CAN_AR if ar else CAN_EN)]
    keep = meaning if meaning['intent'] not in ('unknown', 'conversation') else previous
    remembered = None if reply.get('forget') else {'intent': keep['intent'], 'slots': keep['slots'], **({'asking': True} if reply.get('asking') else {})} if keep else None
    out = {'text': [line for line in reply['text'] if line], 'action': reply.get('action'), 'retry_with_model': reply.get('retry_with_model', False), 'auto_open': bool(reply.get('auto_open')),
           'choices': reply.get('choices') or [], 'meaning': remembered, 'source': source, 'run': view['run'],
           'from_memory': bool(meaning.get('from_memory')), 'chat_id': chat_id}
    # A command on a teaching timetable that is not on screen: open it on the Timetable page first, so the admin sees it.
    act = out['action'] or {}
    if act.get('run_id') and act.get('what') != 'exams' and act.get('type') in ('publish', 'publish_merged', 'rename_run', 'lock_session', 'move_session', 'open') \
            and act['run_id'] != screen.get('run_id'):
        out['show_run'] = act['run_id']
    if chat_id:
        chat = db.get(AssistantChat, chat_id)
        jai_body = {k: out[k] for k in ('text', 'action', 'choices', 'source')} | ({'pending': True} if out['retry_with_model'] else {})
        last = db.scalar(select(AssistantMessage).where(AssistantMessage.chat_id == chat_id).order_by(AssistantMessage.created_at.desc()).limit(1))
        if body.use_model and last and last.role == 'jai' and last.body.get('pending'):
            last.body = jai_body; jai = last  # the local model's answer replaces "Asking the local model…"
        else:
            db.add(AssistantMessage(id=str(uuid4()), chat_id=chat_id, role='you', body={'text': body.text}))
            db.flush()
            jai = AssistantMessage(id=str(uuid4()), chat_id=chat_id, role='jai', body=jai_body)
            db.add(jai)
        if chat.title == 'New chat':
            chat.title = body.text.strip()[:80]
        memory = remember(memory, meaning) if not reply.get('forget') else memory
        if out.get('show_run') or (view['run'] and view['run'].get('on_screen')):
            memory = {**memory, 'run': out.get('show_run') or view['run']['id']}
        action = out.get('action') or {}
        url = action.get('url') or ''
        if action.get('what') == 'exams' or url.startswith('/api/exam-schedules/'):
            ident = action.get('run_id') or url.split('/')[3]
            memory = {**memory, 'exam_run': ident, 'schedule_focus': {'kind': 'exams', 'id': ident}}
        elif url.startswith('/api/schedules/'):
            ident = url.split('/')[3]
            memory = {**memory, 'run': ident, 'schedule_focus': {'kind': 'teaching', 'id': ident}}
        chat.state = {'previous': remembered, 'memory': memory, 'capability_pending': reply.get('pending')}
        chat.updated_at = utcnow()
        db.commit()
        out['message_id'] = jai.id
    return out
