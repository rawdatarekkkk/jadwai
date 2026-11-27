"""Everyday questions JAI answers instantly instead of waiting minutes for the local model:
greetings and thanks, "how many rooms/instructors/…", "list the labs", room features and special
rooms, "what are they?" after a count, and "is the timetable published?"."""
import re

from app.rule_parser import normalise

GREETING = re.compile(r'^(?:hi|hello|hey|good (?:morning|afternoon|evening)|salam|السلام عليكم|سلام|اهلا|مرحبا|صباح الخير|مساء الخير|هاي)(?:\s+(?:jai|there|يا jai))?[\s!.,؟?]*$')
THANKS = re.compile(r'^(?:(?:thanks|thank you|thx|many thanks|great,? thanks|perfect,? thanks)(?:\s+(?:a lot|so much|jai))?|شكرا|شكرا جزيلا|متشكر|متشكرة|تسلم|تسلمي|مرسي)[\s!.,؟?]*$')
COUNT = re.compile(r'(?:\bhow many\b|\bnumber of\b|\btotal\b|كام|عدد)')
KINDS = (
    ('labs', r'\blabs?\b|\blaborator(?:y|ies)\b|معامل|معمل'),
    ('exam_halls', r'\bexam halls?\b|قاعات الامتحان|قاعات امتحان'),
    ('rooms', r'\brooms?\b|\bhalls?\b|\bclassrooms?\b|قاعات|قاعة|قاعه|غرف|غرفة|اوض|اوضة'),
    ('instructors', r'\binstructors?\b|\bteachers?\b|\bdoctors?\b|\bstaff\b|\blecturers?\b|\btas?\b|دكاترة|دكاتره|دكتور|مدرسين|مدرس|اساتذة|اساتذه|استاذ|محاضرين|محاضر|معيدين|معيد'),
    ('students', r'\bstudents?\b|طلاب|طلبة|طلبه|طالب'),
    ('groups', r'\b(?:student )?groups?\b|\bsections?\b|مجموعات|مجموعة|سكاشن|سكشن|شعب|شعبة'),
    ('courses', r'\b(?:teaching )?activities\b|\bcourses?\b|\bsubjects?\b|مواد|مادة|مقررات|مقرر|كورسات|كورس'),
    ('rules', r'\brules?\b|\bconstraints?\b|قيود|قواعد'),
)
LIST = re.compile(r'^(?:please\s+)?(?:list|show(?: me)?|which|what are|give me|اعرض|وريني|ايه|ما هي|هات)\b')
PUBLISHED = re.compile(r'\b(?:is|was|has)\b.*\b(?:timetable|schedule)\b.*\bpublished\b|\bpublished (?:timetable|schedule)\b|\bwhich (?:timetable|schedule|draft) is published\b|(?:الجدول|جدول).*(?:منشور|اتنشر)|(?:منشور|اتنشر).*(?:الجدول|جدول)')
# Room equipment and special-purpose rooms. Projectors and computers are standard, not special.
FEATURES = re.compile(r'\b(?:features?|equipment|equipped|facilities|special(?:i[sz]ed)?|gpus?)\b|مميزات|اجهزة|أجهزة|معدات|تجهيزات|مجهزة|متخصصة|خاصة|مخصوص')
STANDARD = {'projector', 'computers'}
# "What are they?" / "list them" right after a count or list.
THEM = re.compile(r'^(?:and\s+)?(?:(?:what|which) (?:are|r) (?:they|them|those|these)|which ones|(?:list|show(?: me)?|name|give me) (?:them|those|these|the list)|مين هم|مين همه|ايه هما|ايه هي|ايه همه|اعرضهم|وريني هم|وريني(?:هم)?|هاتهم)[\s?.!؟]*$')
NOT_ROOM_QUESTION = re.compile(r'free|availab|busy|empty|vacant|فاضي|فاضية|متاح|\d')


def _say(ar, en, arabic):
    return arabic if ar else en


def _rooms(view, kind=None):
    rows = [r for r in view['records'] if r['kind'] == 'rooms']
    if kind:
        rows = [r for r in rows if kind in (r['data'].get('room_types') or [r['data'].get('room_type')])]
    return sorted(rows, key=lambda r: r['data'].get('code') or r['data'].get('name') or '')


def _special(room):
    return [e for e in room['data'].get('equipment') or [] if e.lower() not in STANDARD]


def _room_line(r, ar, extra=''):
    return f"• {r['data'].get('code') or r['data'].get('name')} · {r['data'].get('capacity', '?')} {_say(ar, 'seats', 'مقعد')}{extra}"


def _listing(kind, view, ar):
    """The records of one kind, for "list the labs" and for "what are they?" after a count."""
    if kind in ('rooms', 'labs', 'exam_halls', 'special_rooms'):
        rows = [r for r in _rooms(view) if _special(r)] if kind == 'special_rooms' else _rooms(view, {'labs': 'lab', 'exam_halls': 'exam_hall'}.get(kind))
        head = {'labs': ('labs', 'معمل'), 'exam_halls': ('exam halls', 'قاعة امتحان'), 'rooms': ('rooms', 'قاعة'),
                'special_rooms': ('rooms with special equipment', 'قاعة بتجهيزات خاصة')}[kind]
        lines = [_room_line(r, ar, f" · {', '.join(_special(r))}" if _special(r) else '') for r in rows]
    elif kind in ('instructors', 'groups', 'courses'):
        rows = sorted((r for r in view['records'] if r['kind'] == kind), key=lambda r: (r['data'].get('code') or '', r['data'].get('name') or ''))
        head = {'instructors': ('instructors', 'مدرس'), 'groups': ('student groups', 'مجموعة طلاب'), 'courses': ('teaching activities', 'نشاط تدريسي')}[kind]
        lines = [f"• {' · '.join(x for x in (r['data'].get('code'), r['data'].get('name')) if x)}" for r in rows]
    else:
        return None
    if not rows:
        return {'text': [_say(ar, 'There are none in the academic data.', 'لا يوجد أي منها في البيانات الأكاديمية.')]}
    one = head[0].replace('rooms with', 'room with') if kind == 'special_rooms' else head[0][:-1]
    out = [_say(ar, f'{len(rows)} {one if len(rows) == 1 else head[0]}:', f'{len(rows)} {head[1]}:')] + lines[:40]
    if len(rows) > 40:
        out.append(_say(ar, f'…and {len(rows) - 40} more on the Academic data page.', f'…و{len(rows) - 40} أخرى في صفحة البيانات الأكاديمية.'))
    return {'text': out, 'listed': kind}


def _features(view, ar):
    """Which equipment the rooms have, and which rooms have the special kinds."""
    rooms = _rooms(view)
    counts = {}
    for r in rooms:
        for e in r['data'].get('equipment') or []:
            counts.setdefault(e, []).append(r['data'].get('code') or r['data'].get('name'))
    if not counts:
        return {'text': [_say(ar, 'No room has any equipment recorded in the academic data.', 'لا توجد أي تجهيزات مسجلة للقاعات في البيانات الأكاديمية.')]}
    lines = [_say(ar, 'Room equipment recorded in the academic data:', 'تجهيزات القاعات المسجلة في البيانات الأكاديمية:')]
    for name, codes in sorted(counts.items(), key=lambda kv: (kv[0].lower() in STANDARD, -len(kv[1]), kv[0])):
        where = ', '.join(codes) if len(codes) <= 4 else _say(ar, f'{len(codes)} rooms', f'{len(codes)} قاعة')
        lines.append(f'• {name}: {where}')
    lines.append(_say(ar, 'A course can require equipment in Course setup; the solver then only uses rooms that have it.',
                      'يمكن أن يتطلب المقرر تجهيزات في إعداد المقررات، وعندها لا يستخدم المُجدول إلا القاعات التي تملكها.'))
    return {'text': lines, 'listed': 'special_rooms'}


def priority_answer(raw, view, ar, memory=None):
    """Questions that the other routes would misread, answered before them: room features and special
    rooms ("what are the features available" is not a free-room question), and "what are they?"."""
    text = normalise(raw)
    if THEM.match(text) and (memory or {}).get('listed'):
        return _listing(memory['listed'], view, ar)
    if FEATURES.search(text) and not re.search(r'\d', text):
        kind = next((k for k, pattern in KINDS if re.search(pattern, text)), None)
        if kind in (None, 'rooms', 'labs', 'exam_halls'):
            if COUNT.search(text) or re.search(r'\bspecial|متخصصة|خاصة|مخصوص', text):
                listing = _listing('special_rooms', view, ar)
                if kind == 'labs' and listing and listing.get('listed'):
                    labs = [r for r in _rooms(view, 'lab') if _special(r)]
                    listing = {'text': [_say(ar, f'{len(labs)} {"lab" if len(labs) == 1 else "labs"} with special equipment:', f'{len(labs)} معمل بتجهيزات خاصة:')]
                               + [_room_line(r, ar, f" · {', '.join(_special(r))}") for r in labs], 'listed': 'special_rooms'}
                return listing
            return _features(view, ar)
    return None


def basic_answer(raw, view, ar):
    """A reply dict ({'text': [...]}) for an everyday question, or None to let the other routes try.
    A reply with 'listed' names the kind a following "what are they?" refers to."""
    text = normalise(raw)
    if GREETING.match(text):
        return {'text': [_say(ar, 'Hello! Ask me about rooms, instructors, groups or the timetable, or ask me to generate or fix one. Say "what can you do?" for examples.',
                              'أهلاً! اسألني عن القاعات أو المدرسين أو المجموعات أو الجدول، أو اطلب مني إنشاء جدول أو إصلاحه. قل «تقدر تعمل إيه؟» لأمثلة.')]}
    if THANKS.match(text):
        return {'text': [_say(ar, "You're welcome.", 'العفو.')]}
    if PUBLISHED.search(text):
        if not view.get('published_id'):
            return {'text': [_say(ar, 'No teaching timetable is published yet. Students and instructors see nothing until you publish one on the Timetable page.',
                                  'لا يوجد جدول تدريس منشور حتى الآن. لن يرى الطلاب والمدرسون شيئاً حتى تنشر جدولاً من صفحة الجدول.')]}
        run = view.get('run') or {}
        name = run.get('name') if run.get('published') else None
        lines = [_say(ar, f'Yes, a teaching timetable is published{f": {name}" if name else ""}. Students and instructors can see it.',
                      f'نعم، يوجد جدول تدريس منشور{f": {name}" if name else ""}، ويستطيع الطلاب والمدرسون رؤيته.')]
        if run.get('published') and run.get('stale'):
            lines.append(_say(ar, 'Your inputs have changed since it was generated, so it may not reflect the latest data.',
                              'تغيّرت بياناتك منذ إنشائه، لذلك قد لا يعكس أحدث البيانات.'))
        return {'text': lines}
    kind = next((k for k, pattern in KINDS if re.search(pattern, text)), None)
    if kind and COUNT.search(text):
        records = view['records']
        if kind in ('rooms', 'labs', 'exam_halls'):
            n = len(_rooms(view, {'labs': 'lab', 'exam_halls': 'exam_hall'}.get(kind)))
            label = {'rooms': ('rooms', 'قاعة'), 'labs': ('labs', 'معمل'), 'exam_halls': ('exam halls', 'قاعة امتحان')}[kind]
        elif kind == 'students':
            groups = [r for r in records if r['kind'] == 'groups']
            n = sum(int(r['data'].get('size') or 0) for r in groups)
            return {'text': [_say(ar, f'{n:,} students in {len(groups)} student groups.', f'{n:,} طالب في {len(groups)} مجموعة.')], 'listed': 'groups'}
        elif kind == 'rules':
            approved = sum(1 for r in view.get('rules', []) if r.get('status') == 'approved')
            total = len(view.get('rules', []))
            return {'text': [_say(ar, f'{total} {"rule" if total == 1 else "rules"}: {approved} approved, {total - approved} waiting for review. Only approved rules are used when generating.',
                                  f'{total} قاعدة: {approved} معتمدة و{total - approved} تنتظر المراجعة. تُستخدم القواعد المعتمدة فقط عند الإنشاء.')]}
        else:
            n = sum(1 for r in records if r['kind'] == kind)
            label = {'instructors': ('instructors', 'مدرس'), 'groups': ('student groups', 'مجموعة طلاب'), 'courses': ('teaching activities', 'نشاط تدريسي')}[kind]
        return {'text': [_say(ar, f'{n} {label[0][:-1] if n == 1 and label[0].endswith("s") else label[0]}.', f'{n} {label[1]}.')], 'listed': kind}
    # "Which rooms are free on Sunday at 10?" is an availability question for the other routes.
    if kind in ('labs', 'exam_halls', 'rooms') and LIST.search(text) and not NOT_ROOM_QUESTION.search(text):
        return _listing(kind, view, ar)
    return None
