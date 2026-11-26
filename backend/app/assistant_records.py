"""JAI creates instructors, rooms and student groups through a short conversation.

Each request is a small form: JAI fills what the first message already says ("add Dr. Sara
Ali to Informatics"), asks for each missing field one at a time (with answer buttons where
the choices are known, while typed answers always work), then shows a summary to confirm.
The browser saves it through the same /api/records endpoint as the Academic data forms,
so the same validation, duplicate-code check and audit apply. Courses have their own
setup page (catalogue, eligibility, groups), so JAI opens it instead.
"""
import re
from app.rule_parser import DAYS, mentions, normalise

KIND_WORDS = {
    'instructors': ('instructor', 'doctor', 'professor', 'lecturer', 'teaching assistant', ' ta ', 'staff member', ' dr ', ' dr. ', ' prof ', ' prof. ', ' د. ', 'دكتور', 'دكتورة', 'معيد', 'معيدة', 'محاضر', 'مدرس', 'عضو هيئة'),
    'rooms': ('room', 'hall', 'lab', 'classroom', 'قاعة', 'قاعه', 'معمل', 'مدرج'),
    'groups': ('group', 'section', 'tutorial group', 'class group', 'جروب', 'مجموعة', 'مجموعه', 'سكشن'),
    'courses': ('course', 'subject', 'مقرر', 'مادة', 'ماده'),
}
ADD_WORDS = ('create', 'add', 'new', 'register', 'make', 'insert', 'ضيف', 'اضف', 'أضف', 'اعمل', 'انشئ', 'أنشئ', 'سجل', 'جديد', 'جديدة')
FIELDS = {'instructors': ('name', 'position', 'department', 'day_off'),
          'rooms': ('code', 'capacity', 'room_types'),
          'groups': ('major', 'year', 'number', 'size')}
NONE_WORDS = ('none', 'no', 'nope', 'no day off', 'not needed', 'skip', 'لا', 'مفيش', 'لأ', 'بدون')
ROOM_TYPES = {'lecture': ('lecture', 'class', 'محاضرات', 'قاعة'), 'lab': ('lab', 'معمل'), 'flexible': ('flexible', 'any', 'مرن'), 'exam_hall': ('exam', 'امتحان', 'امتحانات')}


def record_kind(text):
    """The kind of record a create request is about, '' when it doesn't say what, or None."""
    padded = f' {text} '
    if re.search(r'account|login|user|حساب', text):
        return None  # "create a student account": an account, not a record
    if re.search(r'\b(?:rules?|constraints?|preferences?)\b|قاعدة|قيد', text):
        return None  # "add a rule: Dr. X can't teach Monday": a rule, not a new instructor
    if re.match(r'^(?:i want to |i would like to |i need to |can you |please |عايز |عاوز |محتاج )?(?:add|create|register|اضيف|أضيف|ضيف|اضف|أضف)(?:\s+(?:something|a new one|new|one|حاجة|حاجه))?\s*[.?!]?$', text):
        return ''
    if not any(w in padded for w in ADD_WORDS) or any(w in text for w in ('timetable', 'schedule', 'جدول')):
        return None
    for kind, words in KIND_WORDS.items():
        if any(w in padded for w in words):
            return kind
    return None


def position_of(text):
    if re.search(r'(?<![\w])(ta|t\.a\.|teaching assistant|assistant)(?![\w])|معيد|معيدة', text):
        return 'ta'
    if re.search(r'(?<![\w])(dr\.?|doctor|professor|prof\.?|lecturer)(?![\w])|دكتور|دكتورة|د\.', text):
        return 'doctor'
    return None


def day_of(text):
    for word, day in DAYS.items():
        if mentions(text, normalise(word)):
            return day
    return None


def first_fill(kind, raw, text, view):
    """Fields the first message already gives."""
    form = {}
    if kind == 'instructors':
        name = re.search(r'(?:named|called|name is|name:|اسمه|اسمها|اسم)\s+(.+?)(?:\s*[,،]|\s+(?:in|from|at|who|as|with|في|من)\s|$)', raw, re.I)
        if not name:
            # "add Dr. Sara Ali ..." / "add a TA Omar Adel"
            # Latin names only: Arabic has no capitals to tell a name from "محاضر جديد", so Arabic names need "اسمه".
            name = re.search(r'(?:add|create|register)\s+(?:a\s+|an\s+|new\s+|the\s+)?(?:instructor|TA|ta|teaching assistant|doctor)?\s*((?:[Dd]r\.?\s+|[Pp]rof\.?\s+)?[A-Z][\w.\'-]+(?:\s+[A-Z][\w\'-]+){1,3})', raw)
        if name:
            form['name'] = name.group(1).strip(' .,،')
        if (p := position_of(text)):
            form['position'] = p
        departments = sorted({r['data'].get('department') for r in view['records'] if r['kind'] == 'instructors' and r['data'].get('department')})
        for d in departments:
            if mentions(text, normalise(d)):
                form['department'] = d
        if (d := day_of(text)) and re.search(r'day off|off on|اجازة|إجازة|اجازته|اجازتها', text):
            form['day_off'] = d
    if kind == 'rooms':
        code = re.search(r'(?<![\w])([A-Za-z]{1,3}\d?[.\-]?\d{2,4}[A-Za-z]?)(?![\w])', raw)
        if code:
            form['code'] = code.group(1).upper()
        if (m := re.search(r'(\d{1,4})\s*(?:seats|people|students|capacity|مقعد|طالب|كرسي)', text)) or (m := re.search(r'(?:capacity|for|سعة|يسع)\s*(\d{1,4})', text)):
            form['capacity'] = int(m.group(1))
        types = [t for t, words in ROOM_TYPES.items() if any(w in text for w in words) and t != 'lecture']
        if types:
            form['room_types'] = types
    if kind == 'groups':
        from app.assistant import find_programme, find_year
        progs = find_programme(text, view['records'])
        if len(progs) == 1:
            form['major'] = progs[0]
        if (y := find_year(text)):
            form['year'] = y
        if (m := re.search(r'(?<![\w])(?:g|group|جروب|مجموعة|مجموعه)\s*-?\s*(\d{1,2})(?!\d)', text)):
            form['number'] = int(m.group(1))
        if (m := re.search(r'(\d{1,4})\s*(?:students|طالب|طلاب)', text)):
            form['size'] = int(m.group(1))
    return form


def fill(field, raw, text, view, form):
    """Read the answer to one question; returns the value or None when it can't be read."""
    raw = raw.strip()
    if field == 'name':
        return raw.strip(' .,،') if 2 <= len(raw) <= 100 and not re.fullmatch(r'[\d\W]+', raw) else None
    if field == 'position':
        return position_of(text) or ('doctor' if re.search(r'(?<![\w])d(?![\w])', text) else None)
    if field == 'department':
        return named_answer(field, raw, text, view, form)
    if field == 'day_off':
        if any(re.fullmatch(rf'{w}\.?', text) for w in NONE_WORDS) or text in NONE_WORDS:
            return 'none'
        return day_of(text)
    if field == 'code':
        return raw.upper() if re.fullmatch(r'[\w.\- ]{2,30}', raw) else None
    if field in ('capacity', 'size'):
        m = re.search(r'\d{1,4}', text)
        return int(m.group()) if m and 1 <= int(m.group()) <= 2000 else None
    if field == 'room_types':
        found = [t for t, words in ROOM_TYPES.items() if any(w in text for w in words)]
        return found or None
    if field == 'major':
        return named_answer(field, raw, text, view, form)
    if field == 'year':
        from app.assistant import find_year
        m = find_year(text) or (int(text) if re.fullmatch(r'\d{1,2}', text) else None)
        return m if m and 1 <= m <= 12 else None
    if field == 'number':
        m = re.search(r'\d{1,2}', text)
        return int(m.group()) if m else None
    return None


def named_answer(field, raw, text, view, form):
    """Existing names are references; an unfamiliar label needs explicit consent."""
    from app.assistant import programmes, find_programme
    known = programmes(view['records']) if field == 'major' else sorted({
        r['data'].get('department') for r in view['records']
        if r['kind'] == 'instructors' and r['data'].get('department')})
    pending = form.get('_clarify') or {}
    if pending.get('field') == field and text in ('use as new name', 'انشاء جديد', 'إنشاء جديد'):
        form.pop('_clarify', None)
        form.setdefault('_new_names', {})[field] = pending['raw']
        return pending['raw']
    # Full names and established aliases are safe; partial matches must be unique.
    exact = [name for name in known if normalise(name) == text]
    found = exact or (find_programme(text, view['records']) if field == 'major' else
                      [name for name in known if mentions(text, normalise(name))])
    if len(found) == 1:
        form.pop('_clarify', None)
        return found[0]
    if 2 <= len(raw) <= 100 and not raw.isdigit():
        form['_clarify'] = {'field': field, 'raw': raw, 'matches': found}
    return None


def instructor_code(name, position, records):
    """Same as the Academic data form: D-/T- and initials, numbered when taken."""
    words = re.sub(r'^(dr|prof|eng|mr|ms|mrs)\.?\s+', '', name, flags=re.I).split()
    initials = re.sub(r'[^A-Z0-9؀-ۿ]', '', ''.join(w[0] for w in words).upper())[:6] or 'X'
    base = f"{'T' if position == 'ta' else 'D'}-{initials}"
    taken = {(r['data'].get('code') or '').upper() for r in records if r['kind'] == 'instructors'}
    n = 1
    while (base if n == 1 else f'{base}{n}') in taken:
        n += 1
    return base if n == 1 else f'{base}{n}'


def group_code(major, year, number, records):
    short = ''.join(w[0].upper() for w in re.split(r'[\s,/&-]+', major) if w and w.lower() not in ('and', 'of', 'the')) or 'G'
    base = f'{short}{year or ""}-G{number}'[:17]
    taken = {(r['data'].get('code') or '').upper() for r in records if r['kind'] == 'groups'}
    n = 1
    while (base if n == 1 else f'{base}-{n}').upper() in taken:
        n += 1
    return base if n == 1 else f'{base}-{n}'


def question(kind, field, form, view, say):
    """The question for one missing field, with answer buttons where the answers are known."""
    records = view['records']
    if kind == 'instructors':
        who = form.get('name') or say('the instructor', 'المحاضر')
        if field == 'name':
            return say("What is the instructor's full name?", 'ما الاسم الكامل للمحاضر؟'), []
        if field == 'position':
            return say(f'Is {who} a doctor (teaches lectures) or a TA (tutorials and labs)?', f'هل {who} دكتور (محاضرات) أم معيد (سكاشن ومعامل)؟'), \
                [{'label': say('Doctor', 'دكتور'), 'text': 'doctor'}, {'label': say('TA', 'معيد'), 'text': 'TA'}]
        if field == 'department':
            known = sorted({r['data'].get('department') for r in records if r['kind'] == 'instructors' and r['data'].get('department')})
            return say(f'Which department is {who} in?', f'في أي قسم {who}؟'), [{'label': d, 'text': d} for d in known[:10]]
        if field == 'day_off':
            return say(f'Does {who} have a fixed day off?', f'هل لـ{who} يوم إجازة ثابت؟'), \
                [{'label': say('No day off', 'لا يوجد'), 'text': 'none'}] + [{'label': d, 'text': d} for d in view['calendar']['days']]
    if kind == 'rooms':
        if field == 'code':
            return say('What is the room code (for example C7.201)?', 'ما رمز القاعة (مثلاً C7.201)؟'), []
        if field == 'capacity':
            return say(f"How many seats does {form.get('code', 'the room')} have?", f"كم مقعداً في {form.get('code', 'القاعة')}؟"), []
        if field == 'room_types':
            return say('What is it used for?', 'تُستخدم لماذا؟'), [{'label': say('Lectures', 'محاضرات'), 'text': 'lecture'}, {'label': say('Labs', 'معامل'), 'text': 'lab'},
                                                                      {'label': say('Either', 'الاثنين'), 'text': 'flexible'}, {'label': say('Exams', 'امتحانات'), 'text': 'exam'}]
    if kind == 'groups':
        from app.assistant import programmes
        if field == 'major':
            return say('Which programme is the group in?', 'المجموعة في أي برنامج؟'), [{'label': p, 'text': p} for p in programmes(records)[:10]]
        if field == 'year':
            years = sorted({r['data'].get('year') for r in records if r['kind'] == 'groups' and r['data'].get('major') == form.get('major') and r['data'].get('year')})
            return say(f"Which year of {form.get('major')}?", f"أي سنة في {form.get('major')}؟"), [{'label': say(f'Year {y}', f'سنة {y}'), 'text': str(y)} for y in years or range(1, 5)]
        if field == 'number':
            taken = sorted(int(m.group(1)) for r in records if r['kind'] == 'groups' and r['data'].get('major') == form.get('major') and r['data'].get('year') == form.get('year')
                           and (m := re.search(r'G(\d+)$', r['data'].get('code', ''))))
            nxt = (taken[-1] + 1) if taken else 1
            return say(f'Which group number? The next free one is G{nxt}.', f'رقم المجموعة؟ التالي المتاح G{nxt}.'), [{'label': f'G{nxt}', 'text': f'G{nxt}'}]
        if field == 'size':
            return say('How many students are in the group?', 'كم عدد طلاب المجموعة؟'), []
    return '', []


def body_of(kind, form, view):
    records = view['records']
    if kind == 'instructors':
        return {'name': form['name'], 'code': instructor_code(form['name'], form['position'], records), 'department': form['department'],
                'position': form['position'], 'day_off': None if form.get('day_off') in (None, 'none') else form['day_off'], 'max_weekly_hours': None}
    if kind == 'rooms':
        return {'name': form['code'], 'code': form['code'], 'capacity': form['capacity'], 'room_types': form['room_types']}
    code = group_code(form['major'], form['year'], form['number'], records)
    roman = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
    year = roman[form['year'] - 1] if 1 <= form['year'] <= 12 else f"Year {form['year']}"  # as the existing groups: "Business Informatics I G1"
    return {'name': f"{form['major']} {year} G{form['number']}", 'code': code, 'size': form['size'], 'year': form['year'], 'major': form['major']}


def summary(kind, body, say):
    if kind == 'instructors':
        role = say('doctor', 'دكتور') if body['position'] == 'doctor' else say('TA', 'معيد')
        off = body['day_off'] or say('no fixed day off', 'بدون يوم إجازة')
        return say(f"Add {body['name']} ({role}, {body['department']}, {off}) with code {body['code']}?",
                   f"إضافة {body['name']} ({role}، {body['department']}، {off}) بالرمز {body['code']}؟")
    if kind == 'rooms':
        return say(f"Add room {body['code']}: {body['capacity']} seats, for {', '.join(body['room_types'])}?",
                   f"إضافة القاعة {body['code']}: {body['capacity']} مقعد، لـ {', '.join(body['room_types'])}؟")
    return say(f"Add group {body['code']} ({body['major']}, year {body['year']}, {body['size']} students)?",
               f"إضافة المجموعة {body['code']} ({body['major']}، سنة {body['year']}، {body['size']} طالب)؟")


def converse(slots, view, say):
    """The next step of a create conversation: a question, or the summary to confirm."""
    kind, form = slots['kind'], slots.get('form') or {}
    # Recheck old in-progress chats too: earlier versions accepted arbitrary names.
    for field in ('major', 'department'):
        if field in form and (form.get('_new_names') or {}).get(field) != form[field]:
            value = form[field]
            if named_answer(field, value, normalise(value), view, form) is None:
                form.pop(field)
    slots['form'] = form
    pending = form.get('_clarify')
    if pending:
        field, raw = pending['field'], pending['raw']
        from app.assistant import programmes
        known = programmes(view['records']) if field == 'major' else sorted({
            r['data'].get('department') for r in view['records']
            if r['kind'] == 'instructors' and r['data'].get('department')})
        noun = say('programme', 'برنامج') if field == 'major' else say('department', 'قسم')
        matches = pending.get('matches') or []
        message = say(f'Which {noun} do you mean by "{raw}"? Please choose an existing name or specify the full name. If this is a new {noun}, choose Create new.',
                      f'تقصد أي {noun} بـ "{raw}"؟ اختر اسماً موجوداً أو اكتب الاسم الكامل. لو تقصد اسماً جديداً اختر إنشاء جديد.')
        return {'text': [message], 'asking': True, 'field': field, 'form': form,
                'choices': [{'label': name, 'text': name} for name in (matches or known)] +
                           [{'label': say(f'Create new {noun}: {raw}', f'إنشاء {noun} جديد: {raw}'), 'text': 'use as new name'}]}
    if kind == 'courses':
        return {'text': [say('Courses are set up with their sections, eligible instructors and groups on the Course setup page. I opened it for you.',
                             'تُعد المقررات مع شعبها ومحاضريها ومجموعاتها في صفحة إعداد المقررات. فتحتها لك.')],
                'action': {'type': 'open', 'page': 'data', 'kind': 'courses', 'label': say('Open Course setup', 'فتح إعداد المقررات')}}
    if kind == 'groups' and form.get('number') and form.get('major') and form.get('year') and any(
            r['kind'] == 'groups' and r['data'].get('major') == form['major'] and r['data'].get('year') == form['year']
            and re.search(rf"G{form['number']}$", r['data'].get('code', '')) for r in view['records']):
        taken = form.pop('number')
        return {'text': [say(f"{form['major']} year {form['year']} already has a G{taken}. Which number should the new group have?",
                             f"يوجد بالفعل G{taken} في {form['major']} سنة {form['year']}. ما رقم المجموعة الجديدة؟")],
                'asking': True, 'field': 'number', 'form': form}
    missing = [f for f in FIELDS[kind] if f not in form]
    if missing:
        text, choices = question(kind, missing[0], form, view, say)
        retry = slots.get('unreadable')
        lead = [say("Sorry, I couldn't read that.", 'عذراً، لم أفهم الإجابة.')] if retry else []
        if not form and not retry:
            lead = [say({'instructors': 'Sure, let us add an instructor.', 'rooms': 'Sure, let us add a room.', 'groups': 'Sure, let us add a student group.'}[kind],
                        {'instructors': 'تمام، نضيف محاضراً.', 'rooms': 'تمام، نضيف قاعة.', 'groups': 'تمام، نضيف مجموعة طلاب.'}[kind])]
        return {'text': lead + [text], 'choices': choices, 'asking': True, 'field': missing[0]}
    body = body_of(kind, form, view)
    return {'text': [summary(kind, body, say)],
            'action': {'type': 'create_record', 'kind': kind, 'body': body, 'label': say('Add it', 'إضافة')}}
