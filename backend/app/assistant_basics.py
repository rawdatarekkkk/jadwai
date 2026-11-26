"""Everyday questions JAI answers instantly instead of waiting minutes for the local model:
greetings and thanks, "how many rooms/instructors/…", "list the labs" and "is the timetable published?"."""
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


def _say(ar, en, arabic):
    return arabic if ar else en


def _rooms(view, kind=None):
    rows = [r for r in view['records'] if r['kind'] == 'rooms']
    if kind:
        rows = [r for r in rows if kind in (r['data'].get('room_types') or [r['data'].get('room_type')])]
    return sorted(rows, key=lambda r: r['data'].get('code') or r['data'].get('name') or '')


def basic_answer(raw, view, ar):
    """A reply dict ({'text': [...]}) for an everyday question, or None to let the other routes try."""
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
            return {'text': [_say(ar, f'{n:,} students in {len(groups)} student groups.', f'{n:,} طالب في {len(groups)} مجموعة.')]}
        elif kind == 'rules':
            approved = sum(1 for r in view.get('rules', []) if r.get('status') == 'approved')
            total = len(view.get('rules', []))
            return {'text': [_say(ar, f'{total} {"rule" if total == 1 else "rules"}: {approved} approved, {total - approved} waiting for review. Only approved rules are used when generating.',
                                  f'{total} قاعدة: {approved} معتمدة و{total - approved} تنتظر المراجعة. تُستخدم القواعد المعتمدة فقط عند الإنشاء.')]}
        else:
            n = sum(1 for r in records if r['kind'] == kind)
            label = {'instructors': ('instructors', 'مدرس'), 'groups': ('student groups', 'مجموعة طلاب'), 'courses': ('teaching activities', 'نشاط تدريسي')}[kind]
        return {'text': [_say(ar, f'{n} {label[0][:-1] if n == 1 and label[0].endswith("s") else label[0]}.', f'{n} {label[1]}.')]}
    # "Which rooms are free on Sunday at 10?" is an availability question for the other routes.
    if kind in ('labs', 'exam_halls', 'rooms') and LIST.search(text) and not re.search(r'free|availab|busy|empty|vacant|فاضي|فاضية|متاح|\d', text):
        rows = _rooms(view, {'labs': 'lab', 'exam_halls': 'exam_hall'}.get(kind))
        if not rows:
            return {'text': [_say(ar, 'There are none in the academic data.', 'لا يوجد أي منها في البيانات الأكاديمية.')]}
        shown = rows[:40]
        head = {'labs': ('labs', 'معمل'), 'exam_halls': ('exam halls', 'قاعة امتحان'), 'rooms': ('rooms', 'قاعة')}[kind]
        lines = [_say(ar, f'{len(rows)} {head[0][:-1] if len(rows) == 1 else head[0]}:', f'{len(rows)} {head[1]}:')]
        lines += [f"• {r['data'].get('code') or r['data'].get('name')} · {r['data'].get('capacity', '?')} {_say(ar, 'seats', 'مقعد')}" for r in shown]
        if len(rows) > len(shown):
            lines.append(_say(ar, f'…and {len(rows) - len(shown)} more on the Academic data page.', f'…و{len(rows) - len(shown)} أخرى في صفحة البيانات الأكاديمية.'))
        return {'text': lines}
    return None
