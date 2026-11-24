"""What an Ask JAI chat remembers, so later messages can refer back.

After each understood message the chat keeps the last room, instructor, group, course,
programme, year, days and time it talked about. A later message that leaves them out
or points back ("is it free at 2?", "what about Monday?", "and G8?", "generate it",
"هي فاضية الساعة 2؟") is completed from that memory. Only the chat's own memory is
used: a new chat starts empty.
"""
import re

SUBJECTS = {'rooms': 'room_schedule', 'instructors': 'instructor_schedule', 'groups': 'group_schedule', 'courses': 'course_schedule'}
KIND_OF = {v: k for k, v in SUBJECTS.items()}
POINTING = ('it', 'its', 'that', 'there', 'he', 'she', 'him', 'her', 'his', 'they', 'them', 'their', 'this', 'same', 'that one', 'this one',
            'هو', 'هي', 'ده', 'دي', 'دا', 'فيها', 'فيه', 'عنده', 'عندها', 'عندهم', 'بتاعه', 'بتاعها', 'نفس', 'هما', 'هم')
FOLLOW_UP = ('and ', 'what about', 'how about', 'also ', 'و', 'طب ', 'طيب ', 'وماذا عن', 'وايه عن', 'طب و')


def points_back(text):
    words = set(re.findall(r'[\w؀-ۿ]+', text))
    return any((w in words) if ' ' not in w else (w in text) for w in POINTING)


# Words that point back at what the chat is about, longest first ("the group I just created" before "it").
REFERENCES = sorted({
    'the group i just created', 'the group i just added', 'the group i created', 'the new group', 'that group', 'this group', 'the same group',
    'the room i just created', 'the room i just added', 'the new room', 'that room', 'this room', 'the same room',
    'the instructor i just created', 'the instructor i just added', 'the new instructor', 'that instructor', 'this instructor', 'the same instructor',
    'that course', 'this course', 'the same course', 'the one i just created', 'the one i just added', 'the new one', 'that one', 'this one',
    'them', 'they', 'their', 'it', 'its', "it's", 'him', 'her', 'his', 'he', 'she',
    'المجموعة الجديدة', 'المجموعة دي', 'القاعة الجديدة', 'القاعة دي', 'المحاضر الجديد', 'اللي لسه عملتها', 'اللي لسه عملته', 'اللي عملتها', 'اللي عملته',
    'الجديدة', 'الجديد', 'هم', 'هما', 'هي', 'هو', 'ليهم', 'لهم'}, key=len, reverse=True)
NOT_A_RECORD = ('publish', 'unpublish', 'stop', 'cancel', 'rename', 'انشر', 'الغي', 'وقف')


def remember_record(memory, kind, ident):
    """The chat is now about this record (just created, edited or named)."""
    memory = dict(memory or {})
    if kind in SUBJECTS and ident:
        memory[kind] = [ident] + [i for i in memory.get(kind, []) if i != ident][:4]
        memory['subject'] = kind
    return memory


HERE = r'(?<![\w])(?:here|there|in it|to it|in this (?:programme|program|year|major)|in that (?:programme|program|year|major)|the same (?:programme|program|year|major)|هنا|هناك|فيها|فيه|في نفس السنة|في نفس البرنامج)(?![\w])'


def place_of(text, memory):
    """'Here' / 'in this year': the programme and year the chat was just about, as {'major', 'year'}."""
    if not (memory or {}).get('programmes') or not re.search(HERE, text.lower()):
        return {}
    out = {'major': memory['programmes'][0]}
    if memory.get('year'):
        out['year'] = memory['year']
    return out


def resolve_references(text, memory, view):
    """'create a schedule for them' -> 'create a schedule for IS3-G4' when the chat is about that group."""
    kind = (memory or {}).get('subject')
    ident = ((memory or {}).get(kind) or [None])[0] if kind in SUBJECTS else None
    record = next((r for r in view['records'] if r['id'] == ident), None)
    if not record:
        return text, None
    name = record['data'].get('name') if kind == 'instructors' else record['data'].get('code') or record['data'].get('name')
    lowered = text.lower()
    if any(w in lowered for w in NOT_A_RECORD):
        return text, None
    for phrase in REFERENCES:
        pattern = r'(?<![\w\u0600-\u06FF])' + re.escape(phrase) + r'(?![\w\u0600-\u06FF])'
        if re.search(pattern, lowered):
            replacement = name + ("'s" if phrase in ('its', "it's", 'their', 'his', 'her') else '')
            return re.sub(pattern, lambda _: replacement, text, count=1, flags=re.I), name
    return text, None


def remember(memory, meaning):
    """Update the chat's memory from an understood message."""
    intent, slots = meaning.get('intent'), meaning.get('slots') or {}
    from app.assistant import TASKS
    if intent in ('programme_info', 'generate_timetable', 'improve_schedule') or (intent == 'create_record' and (slots.get('form') or {}).get('major')):
        # "Which groups are in BI year 1?" then "add a group here": the programme and year being talked about.
        memory = dict(memory or {})
        progs = slots.get('programmes') or ([slots['form']['major']] if (slots.get('form') or {}).get('major') else [])
        year = slots.get('year') or (slots.get('form') or {}).get('year')
        if progs:
            memory['programmes'], memory['place'] = list(progs)[:3], True
            memory['year'] = year
        if intent != 'programme_info':
            return memory
    if intent == 'programme_info':
        return memory
    if intent == 'split_group':
        return remember_record(memory, 'groups', slots.get('group'))
    if intent in ('edit_record', 'delete_record', 'record_info'):
        for kind, ident in (slots.get('targets') or [])[:1]:
            memory = remember_record(memory, kind, ident)
        return memory
    if intent == 'create_account':
        form = slots.get('form') or {}
        if form.get('group_id'):
            memory = remember_record(memory, 'groups', form['group_id'])
        if form.get('instructor_id'):
            memory = remember_record(memory, 'instructors', form['instructor_id'])
        return memory
    if intent in ('unknown', 'cancel', 'help', 'create_record', 'status', 'publish', 'unpublish', *TASKS) and intent not in ('move_session', 'lock_session'):
        return memory
    memory = dict(memory or {})
    for kind in SUBJECTS:
        if slots.get(kind):
            memory[kind] = list(slots[kind])[:5]
            memory['subject'] = kind
    if intent in KIND_OF and slots.get(KIND_OF[intent]):
        memory['subject'] = KIND_OF[intent]
    if intent == 'free_rooms':
        memory['subject'] = 'free_rooms'
    for key in ('programmes', 'days'):
        if slots.get(key):
            memory[key] = list(slots[key])
    if slots.get('year'):
        memory['year'] = slots['year']
    if slots.get('window'):
        memory['window'] = list(slots['window'])
    if slots.get('lab') is not None and intent == 'free_rooms':
        memory['lab'], memory['seats'] = slots.get('lab'), slots.get('seats')
    return memory


EXPLICIT_EXAM = r'\b(exams?|midterms?|finals?|quizzes)\b|امتحان|ميدترم|نهائي'
EXPLICIT_TEACHING = r'\b(teaching|weekly|lectures?|classes)\b|تدريس|اسبوعي|الأسبوعي|محاضرات'


def with_context(text, meaning, memory):
    """Complete a message from the chat's memory when it leaves things out or points back."""
    # The schedule being discussed survives PDFs, renaming and other follow-ups.
    related = ('download_pdf', 'exam_pdf', 'publish', 'unpublish', 'rename_run', 'export_csv')
    if meaning['intent'] in related:
        explicit_exam = bool(re.search(EXPLICIT_EXAM, text.lower()))
        explicit_teaching = bool(re.search(EXPLICIT_TEACHING, text.lower()))
        focus = (memory or {}).get('schedule_focus') or {}
        kind = 'exams' if explicit_exam else 'teaching' if explicit_teaching else focus.get('kind')
        if not kind and (memory or {}).get('exam_run') and not (memory or {}).get('run'):
            kind = 'exams'  # compatibility for chats created before schedule_focus
        if kind:
            meaning = {**meaning, 'slots': {**meaning['slots'], 'exams': kind == 'exams', 'schedule_kind': kind}}
            if meaning['intent'] == 'download_pdf' and kind == 'exams':
                meaning['intent'] = 'exam_pdf'
            elif meaning['intent'] == 'exam_pdf' and kind == 'teaching':
                meaning['intent'] = 'download_pdf'
    from app.assistant import TASKS
    if not memory or meaning.get('follow_up') or meaning['intent'] in ('create_record', 'cancel', 'help', 'exam_timetable', 'status', 'publish', 'unpublish', *TASKS):
        return meaning
    from app.assistant import ASK_WORDS, SCHEDULE_WORDS, has
    intent, slots = meaning['intent'], dict(meaning['slots'])
    named = any(slots.get(k) for k in SUBJECTS)
    when = bool(slots.get('days') or slots.get('window'))
    back = points_back(text)
    subject = memory.get('subject')
    # Missing day: the remembered one. Missing time: the remembered one, unless a new day was named (then the whole day).
    keep_time = lambda s: {**s, 'days': s.get('days') or memory.get('days', []),
                           'window': s.get('window') or (memory.get('window') if not s.get('days') else None)}

    # "Is it free at 2?" / "her schedule on Monday" / "what about 10:00?": the remembered subject.
    if not named and subject and (intent == 'unknown' or intent in KIND_OF) and (back or when or has(text, ASK_WORDS + SCHEDULE_WORDS)):
        if subject == 'free_rooms':
            return {**meaning, 'intent': 'free_rooms', 'slots': {**keep_time(slots), 'lab': memory.get('lab'), 'seats': memory.get('seats')}, 'from_memory': True}
        if memory.get(subject):
            return {**meaning, 'intent': SUBJECTS[subject], 'slots': {**keep_time(slots), subject: memory[subject]}, 'from_memory': True}

    # "And G8?" / "what about Dr. Ahmed?": a new subject, the same day and time as before.
    short = len(text.split()) <= 5 or text.startswith(FOLLOW_UP)
    if named and intent in KIND_OF and not when and short and (memory.get('days') or memory.get('window')):
        return {**meaning, 'slots': keep_time(slots), 'from_memory': True}

    # "Generate it" / "download the pdf for that group": the remembered group, or programme and year.
    if intent in ('generate_timetable', 'download_pdf') and back and not (slots.get('groups') or slots.get('programmes') or slots.get('year') or slots.get('everything')):
        if memory.get('groups') and subject == 'groups':
            return {**meaning, 'slots': {**slots, 'groups': memory['groups'][:1]}, 'from_memory': True}
        if memory.get('programmes'):
            return {**meaning, 'slots': {**slots, 'programmes': memory['programmes'], 'year': memory.get('year')}, 'from_memory': True}
    return meaning
