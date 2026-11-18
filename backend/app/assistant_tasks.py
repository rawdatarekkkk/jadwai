from urllib.parse import quote
"""The rest of the website through Ask JAI: constraints, editing and deleting records, accounts,
moving and locking sessions, renaming and stopping drafts, reports and exports, input checks,
exam questions, and opening any page.

Everything that changes data comes back as an action the admin confirms; the browser then calls
the same endpoint the page would, so every check, lock, validation and audit entry still applies.
Things that need a file or a long form (importing a spreadsheet, semester settings, course setup,
advising students) open the page that does them.
"""
import re
from app.rule_parser import find_records, mentions, normalise, parse, plain

PAGES = {  # page: words that name it (English, Arabic)
    'overview': ('overview', 'home page', 'dashboard', 'الرئيسية'),
    'data': ('academic data', 'data page', 'records page', 'البيانات الاكاديمية', 'البيانات'),
    'courses': ('course setup', 'courses page', 'اعداد المقررات', 'المقررات'),
    'constraints': ('constraints page', 'constraints', 'rules page', 'القيود'),
    'timetable': ('timetable page', 'teaching timetable', 'جدول التدريس'),
    'exams': ('exam page', 'exams page', 'exam timetable page', 'الامتحانات'),
    'accounts': ('accounts page', 'accounts', 'users page', 'الحسابات'),
    'activity': ('activity log', 'activity page', 'سجل النشاط'),
    'evaluation': ('evaluation page', 'evaluation', 'التقييم'),
    'proposals': ('proposal review', 'proposals page', 'proposals', 'المقترحات'),
    'settings': ('semester settings', 'settings', 'calendar settings', 'الاعدادات'),
    'import': ('import page', 'import', 'استيراد'),
    'advising': ('advising students', 'advising', 'طلاب الارشاد', 'الارشاد'),
}
PAGE_NAMES = {'overview': ('Overview', 'الرئيسية'), 'data': ('Academic data', 'البيانات الأكاديمية'), 'courses': ('Course setup', 'إعداد المقررات'),
              'constraints': ('Constraints', 'القيود'), 'timetable': ('Timetable', 'الجدول'), 'exams': ('Exams', 'الامتحانات'), 'accounts': ('Accounts', 'الحسابات'),
              'activity': ('Activity log', 'سجل النشاط'), 'evaluation': ('Evaluation', 'التقييم'), 'proposals': ('Proposal review', 'مراجعة المقترحات'),
              'settings': ('Semester settings', 'إعدادات الفصل'), 'import': ('Import data', 'استيراد البيانات'), 'advising': ('Advising students', 'طلاب الإرشاد')}
OPEN_VERB = r'^(?:please\s+)?(?:open|go to|show me the|show the|take me to|navigate to|bring up|افتح|روح|وديني|اعرض)\b\s*'
RULE_CUES = ('can\'t', 'cant', 'cannot', 'not available', 'unavailable', 'no classes', 'no class', 'no lectures', 'prefer', 'prefers', 'only', 'at most',
             'no more than', 'maximum', 'max ', 'must be in', 'must not', 'not on the same day', 'day off', 'never', 'avoid', 'not before', 'not after',
             'مش متاح', 'غير متاح', 'مش فاضي', 'لا يستطيع', 'مينفعش', 'يفضل', 'فقط', 'بس', 'بحد أقصى', 'بحد اقصى', 'لا يزيد', 'ممنوع', 'مفيش محاضرات', 'إجازة', 'اجازة')
QUESTION_START = r'^(?:is|are|was|when|what|who|which|where|does|do|can you|could you|how|هل|امتى|امتي|متى|متي|مين|ايه|فين|إمتى)\b'  # normalise turns ى into ي
ROLE_WORDS = {'student': ('student', 'طالب', 'طالبة'), 'instructor': ('instructor', 'doctor', 'ta ', 'teacher', 'lecturer', 'محاضر', 'دكتور', 'معيد'),
              'administrator': ('admin', 'administrator', 'مدير', 'ادمن'), 'viewer': ('viewer', 'read-only', 'read only', 'مشاهد')}
EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+')


def H(text, words):
    return any(w in text for w in words)


def named(text, view, kinds=('rooms', 'instructors', 'groups', 'courses')):
    """Records the text names: [(kind, record)], groups by code or programme+year+number too."""
    from app.assistant import find_group, find_programme, find_year
    found = []
    for kind in kinds:
        if kind == 'groups':
            for g in find_group(text, view['records'], find_programme(text, view['records']), find_year(text)):
                found.append(('groups', g))
            continue
        rows, _ = find_records(text, view['records'], kind)
        found += [(kind, r) for r in rows]
    return found


def understand_task(raw, text, view):
    """The website tasks below, or None to let the other patterns try."""
    # "show the draft", "open the schedule", "show schedule": the timetable this chat is about, on the Timetable page.
    if re.fullmatch(r'(?:please\s+)?(?:show|open|view|see|display|bring up|اعرض|افتح|وريني)\s+(?:me\s+)?(?:(?:the|this|that|my|our|it|new|latest|newest|generated|current|الـ?)\s+)*'
                    r'(?:draft|schedule|timetable|مسودة|المسودة|الجدول|جدول)(?:\s+(?:you|we|i)\s+(?:just\s+)?(?:made|generated|created))?\s*(?:please)?[.!?]?', text):
        return {'intent': 'show_run', 'slots': {}}
    if re.match(OPEN_VERB, text):
        rest = re.sub(OPEN_VERB, '', text)
        for page, words in PAGES.items():
            if H(rest, words):
                return {'intent': 'open_page', 'slots': {'page': page}}
    asks_about = re.search(r'^(?:please\s+)?(?:show|list|what|which|how many|tell me|give me|اعرض|وريني|ايه|كام|مين)\b', text) or text.endswith(('?', '؟')) or H(text, ('available', 'are there', 'موجودة', 'المتاحة'))
    if asks_about and re.search(r'\b(?:study )?years?\b|سنين|السنوات|سنوات|الفرق', text) and not re.search(r'\b(?:free|off)\b', text) \
            and not re.search(r'\bgroups?\b|مجموعات|جروبات', text):
        from app.assistant import find_programme
        return {'intent': 'programme_info', 'slots': {'programmes': find_programme(text, view['records']), 'what': 'years'}}
    if asks_about and re.search(r'\bgroups?\b|مجموعات|جروبات', text) and not named(text, view, ('instructors', 'rooms', 'courses')):
        from app.assistant import find_programme, find_year
        return {'intent': 'programme_info', 'slots': {'programmes': find_programme(text, view['records']), 'year': find_year(text), 'what': 'groups'}}
    if asks_about and re.search(r'\bprogrammes?\b|\bprograms?\b|\bmajors?\b|البرامج|التخصصات', text):
        return {'intent': 'programme_info', 'slots': {'programmes': [], 'what': 'programmes'}}
    if re.search(r'(import|upload|load).*(excel|spreadsheet|file|xlsx|csv|data)|(استيراد|ارفع|رفع)', text) and not H(text, ('export',)):
        return {'intent': 'open_page', 'slots': {'page': 'import', 'why': 'file'}}
    if H(text, ('teaching days', 'teaching periods', 'semester dates', 'term name', 'semester name', 'period times', 'break time', 'lunch break', 'مواعيد الفترات', 'ايام الدراسة', 'أيام الدراسة')):
        return {'intent': 'open_page', 'slots': {'page': 'settings', 'why': 'settings'}}
    if H(text, ('advising student', 'irregular student', 'retake student', 'طالب ارشاد', 'طالب إرشاد', 'طلاب الارشاد')):
        return {'intent': 'open_page', 'slots': {'page': 'advising', 'why': 'advising'}}
    if re.search(r'(stop|cancel|abort|halt|kill|اوقف|وقف|الغي|ألغي).{0,30}(generat|run|solver|انشاء|إنشاء|توليد|المحلل)', text):
        return {'intent': 'cancel_run', 'slots': {}}
    m = re.search(r'(?:rename|call|name)\s+(?:this|the|it|my)?\s*(draft|timetable|schedule|exam timetable|exams?)?\s*(?:to|as|:)\s*(.+)$', raw, re.I) or \
        re.search(r'(?:سمي|سمّي|غير اسم)\s*(?:ال)?(مسودة|جدول|الجدول|الامتحانات)?\s*(?:الى|إلى|ل|:)?\s*(.+)$', raw)
    if m and not named(text, view, ('rooms', 'instructors', 'groups')):
        return {'intent': 'rename_run', 'slots': {'name': m.group(2).strip(' "\'“”.'), 'exams': bool(re.search(r'exam|امتحان', (m.group(1) or '').lower()))}}
    if H(text, ('statistics', 'stats', 'report', 'how good', 'quality of', 'convenience', 'preference satisfaction', 'تقرير', 'احصائيات', 'إحصائيات', 'جودة')):
        return {'intent': 'statistics', 'slots': {}}
    if H(text, ('csv', 'export to excel', 'as excel', 'spreadsheet')) and not H(text, ('import',)):
        return {'intent': 'export_csv', 'slots': {'exams': H(text, ('exam', 'امتحان'))}}
    if re.search(r'\b(?:split|divide|قسم|قسّم)\b', text) and H(text, ('two', '2', 'halves', 'half', 'اتنين', 'نصين', 'مجموعتين', 'group')):
        target = [r for k, r in named(text, view, ('groups',))]
        if target:
            return {'intent': 'split_group', 'slots': {'group': target[0]['id']}}
    if re.search(r'^(?:please\s+)?(?:fix|solve|repair|resolve|صلح|اصلح|حل)\b', text) or H(text, ('fix the problem', 'fix these', 'fix it', "why can't i generate", 'why cant i generate',
                                                                                     'why did it fail', 'what went wrong', 'what stopped', 'حل المشاكل', 'صلح المشاكل', 'ليه وقف')):
        return {'intent': 'fix_problems', 'slots': {}}
    if H(text, ('input check', 'can i generate', 'ready to generate', 'what is blocking', "what's blocking", 'what blocks', 'blockers', 'preflight',
                'check the data', 'check inputs', 'check my data', 'problems with the data', 'is the data ready', 'الفحوص', 'جاهز للانشاء', 'ايه اللي مانع')):
        return {'intent': 'input_checks', 'slots': {}}
    exam = next((k for k, w in (('final', ('final', 'نهائي', 'فاينل')), ('midterm', ('midterm', 'ميدترم', 'منتصف')), ('quiz', ('quiz', 'كويز'))) if H(text, w)), None)
    if (exam or H(text, ('exam', 'امتحان'))) and H(text, ('pdf', 'print', 'طباعة')):
        return {'intent': 'exam_pdf', 'slots': {}}
    if (exam or H(text, ('exam', 'امتحان'))) and re.search(QUESTION_START + r'|when|time|date|امتى|امتي|متي|موعد|معاد|ميعاد', text):
        courses = [r['id'] for k, r in named(text, view, ('courses',))]
        if courses:
            return {'intent': 'exam_when', 'slots': {'courses': courses, 'exam_kind': exam}}
    from app.assistant import days_in, period_of
    if re.search(r'^(?:please\s+|can you\s+|could you\s+)?(?:move|reschedule|shift|put|انقل|حرك|غير ميعاد)\b', text) and (
            named(text, view, ('courses',)) or [d for d in days_in(text, view['calendar']) if d] or period_of(text, view['calendar'])):
        source, target = split_move(raw)
        return {'intent': 'move_session', 'slots': {'source': source, 'target': target}}
    if re.search(r'^(?:please\s+)?(?:lock|pin|freeze|keep|ثبت|اقفل|ثبّت)\b', text):
        return {'intent': 'lock_session', 'slots': {'source': raw, 'target': ''}}
    info = ('how many students', 'how many seats', 'capacity', 'what size', 'how big', 'size of', 'details', 'info about', 'information about', 'which department',
            'what department', 'day off', 'what position', 'is he a', 'is she a', 'كام طالب', 'كام مقعد', 'سعة', 'عدد طلاب', 'بيانات', 'معلومات', 'قسم')
    asks = re.search(QUESTION_START, text) or text.endswith('?') or text.endswith('؟')
    editing = re.search(r'\b(?:change|set|update|edit|increase|decrease|raise|lower|reduce|bump|adjust|عدل|غير|خلي|زود|قلل)\b', text)
    if editing:
        pass
    elif (H(text, info) and (asks or H(text, ('details', 'info', 'بيانات', 'معلومات')))) or \
            (asks and H(text, ('size', 'seats', 'students', 'department', 'position', 'سعة', 'طلاب', 'قسم')) and not H(text, ('free', 'available', 'فاضي', 'متاح'))):
        target = named(text, view, ('rooms', 'instructors', 'groups'))
        if target:
            return {'intent': 'record_info', 'slots': {'targets': [(k, r['id']) for k, r in target][:3]}}
    if re.search(r'(account|login|user|حساب|يوزر)', text):
        if re.search(r'(reset|new password|forgot|setup link|set-up link|send.*link|password link|اعادة تعيين|إعادة تعيين|باسورد جديد|كلمة سر جديدة|نسي)', text):
            return {'intent': 'reset_account', 'slots': {'raw': raw}}
        if re.search(r'(create|add|make|open|new|register|اعمل|انشئ|أنشئ|ضيف|اضف|أضف|جديد)', text):
            return {'intent': 'create_account', 'slots': {'form': account_fill(raw, text, view)}}
        if re.search(r'(list|show|who has|how many|which|اعرض|مين عنده|كام)', text):
            return {'intent': 'list_accounts', 'slots': {}}
    if re.search(r'(reset|new) password|setup link|اعادة تعيين|باسورد جديد', text):
        return {'intent': 'reset_account', 'slots': {'raw': raw}}
    is_rule = H(text, ('rule', 'constraint', 'قيد', 'قيود'))
    if is_rule and re.search(r'(list|show|what are|which|see|اعرض|ايه|وريني)', text):
        return {'intent': 'list_rules', 'slots': {'about': [r['id'] for k, r in named(text, view)]}}
    if is_rule and re.search(r'^(?:please\s+)?(remove|delete|drop|احذف|امسح|شيل)', text):
        return {'intent': 'remove_rule', 'slots': {'about': [r['id'] for k, r in named(text, view)], 'words': text}}
    if is_rule and re.search(r'approve|اعتمد|وافق', text):
        return {'intent': 'approve_rules', 'slots': {}}
    if re.search(r'^(?:please\s+)?(?:delete|remove|احذف|امسح|شيل)\b', text):
        target = named(text, view)
        if target:
            return {'intent': 'delete_record', 'slots': {'targets': [(k, r['id']) for k, r in target][:3]}}
    edit_verb = r'(?:change|set|update|make|edit|rename|increase|decrease|raise|lower|reduce|bump|adjust|عدل|غير|خلي|زود|قلل)'
    polite = r'^(?:please\s+|can you\s+|could you\s+|i want to\s+|i would like to\s+|i\'d like to\s+|let\'s\s+|عايز\s+|ممكن\s+)?'
    field_words = ('capacity', 'seats', 'size', 'students', 'day off', 'position', 'department', 'type', 'code', 'name', 'سعة', 'مقعد', 'عدد', 'اجازة', 'إجازة', 'قسم', 'نوع')
    if re.search(polite + edit_verb + r'\b', text) or (re.search(r'\b' + edit_verb + r'\b', text) and H(text, field_words) and re.search(r'\d|to ', text)):
        target = named(text, view, ('rooms', 'instructors', 'groups'))
        if target:
            return {'intent': 'edit_record', 'slots': {'targets': [(k, r['id']) for k, r in target][:2], 'raw': raw}}
    from app.assistant_improve import goals_in, target_groups, wants_improvement
    if wants_improvement(text) and not named(text, view, ('instructors', 'rooms')):
        # "Give BA5-G7 two free days" / "a better timetable for IT Security year 3": analyse, propose, regenerate.
        return {'intent': 'improve_schedule', 'slots': {'goals': goals_in(text, view['calendar']), 'groups': target_groups(text, view)}}
    if H(f' {text} ', RULE_CUES) and not re.search(QUESTION_START, text) and not text.endswith('?') and (named(text, view) or H(text, ('lecture', 'tutorial', 'lab', 'classes', 'constraint', 'قيد', 'محاضر', 'سكشن'))) \
            and not re.match(r'(?:please\s+)?(?:publish|unpublish|انشر|نشر)', text):  # "publish G7 only" is not a rule
        return {'intent': 'add_rule', 'slots': {'raw': raw}}
    return None


def account_fill(raw, text, view):
    form = {}
    if (m := EMAIL.search(raw)):
        form['email'] = m.group().strip('.,')
    for role, words in ROLE_WORDS.items():
        if H(f' {text} ', words):
            form['role'] = role
            break
    if form.get('role') == 'instructor':
        rows, _ = find_records(text, view['records'], 'instructors')
        if len(rows) == 1:
            form['instructor_id'], form['name'] = rows[0]['id'], rows[0]['data']['name']
    if form.get('role') == 'student':
        from app.assistant import find_group, find_programme, find_year
        g = find_group(text, view['records'], find_programme(text, view['records']), find_year(text))
        if len(g) == 1:
            form['group_id'] = g[0]['id']
    if (m := re.search(r'(?:named|called|name is|for|اسمه|اسمها|ل)\s+((?:dr\.?\s+)?[A-Z][\w\'-]+(?:\s+[A-Z][\w\'-]+){1,3})', raw)) and 'name' not in form:
        form['name'] = m.group(1)
    return form


def account_step(slots, view, say):
    form = slots.get('form') or {}
    if not form.get('role'):
        return {'text': [say('What kind of account?', 'ما نوع الحساب؟')], 'asking': True, 'field': 'role',
                'choices': [{'label': say('Student', 'طالب'), 'text': 'student'}, {'label': say('Instructor', 'محاضر'), 'text': 'instructor'},
                            {'label': say('Administrator', 'مدير'), 'text': 'administrator'}, {'label': say('Viewer (read-only)', 'مشاهد'), 'text': 'viewer'}]}
    if form['role'] == 'instructor' and not form.get('instructor_id'):
        return {'text': [say('Which instructor is the account for?', 'الحساب لأي محاضر؟')], 'asking': True, 'field': 'instructor_id'}
    if form['role'] == 'student' and not form.get('group_id'):
        return {'text': [say("Which student group is the student in (for example BA5-G7)?", 'الطالب في أي مجموعة (مثلاً BA5-G7)؟')], 'asking': True, 'field': 'group_id'}
    if not form.get('name'):
        return {'text': [say('What name should the account show?', 'ما الاسم الذي يظهر للحساب؟')], 'asking': True, 'field': 'name'}
    if not form.get('email'):
        return {'text': [say(f"What is {form['name']}'s email? It is used to sign in.", f"ما بريد {form['name']}؟ يُستخدم لتسجيل الدخول.")], 'asking': True, 'field': 'email'}
    if any(u['email'] == form['email'].lower() for u in view.get('users', [])):
        form.pop('email')
        return {'text': [say('That email already has an account. Which email should the new account use?', 'هذا البريد له حساب بالفعل. ما البريد الآخر؟')], 'asking': True, 'field': 'email', 'form': form}
    names = {r['id']: r['data'].get('code') or r['data'].get('name') for r in view['records']}
    link = f" ({names.get(form.get('group_id') or form.get('instructor_id'), '')})" if form.get('group_id') or form.get('instructor_id') else ''
    role = {'student': say('student', 'طالب'), 'instructor': say('instructor', 'محاضر'), 'administrator': say('administrator', 'مدير'), 'viewer': say('viewer', 'مشاهد')}[form['role']]
    body = {'name': form['name'], 'email': form['email'].lower(), 'role': form['role'], **{k: form[k] for k in ('group_id', 'instructor_id') if form.get(k)}}
    article = 'an' if role[0] in 'aeiou' else 'a'
    return {'text': [say(f"Create {article} {role} account for {form['name']}{link}, {body['email']}? You'll get a one-time setup link to send them; it expires in 30 minutes.",
                         f"إنشاء حساب {role} لـ{form['name']}{link}، {body['email']}؟ ستحصل على رابط إعداد لمرة واحدة ترسله له؛ ينتهي بعد 30 دقيقة.")],
            'action': {'type': 'create_account', 'body': body, 'label': say('Create account', 'إنشاء الحساب')}}


def account_answer(field, raw, text, view):
    if field == 'role':
        return next((r for r, w in ROLE_WORDS.items() if H(f' {text} ', w) or text.strip() == r), None)
    if field == 'instructor_id':
        rows, _ = find_records(text, view['records'], 'instructors')
        return rows[0]['id'] if len(rows) == 1 else None
    if field == 'group_id':
        from app.assistant import find_group, find_programme, find_year
        g = find_group(text, view['records'], find_programme(text, view['records']), find_year(text))
        return g[0]['id'] if len(g) == 1 else None
    if field == 'name':
        return raw.strip(' .,') if 2 <= len(raw.strip()) <= 100 else None
    if field == 'email':
        m = EMAIL.search(raw)
        return m.group().strip('.,') if m else None
    return None


def rule_line(rule, view, say):
    """A readable rule: 'Dr. X unavailable · Sunday 08:00–10:30 · required'."""
    names = {r['id']: r['data'].get('code') if r['kind'] in ('rooms', 'groups') else r['data'].get('name') for r in view['records']}
    who = names.get(rule.get('instructor_id') or rule.get('room_id') or rule.get('group_id') or rule.get('activity_id'), '')
    if rule.get('type') in ('teaching_allowed', 'teaching_preferred'):
        who = say('All groups', 'كل المجموعات') + ' · ' + ', '.join((rule.get('params') or {}).get('activity_types') or [])
    hours = lambda h: f'{int(h):02d}:{int(round((h % 1) * 60)):02d}'
    when = ' '.join(x for x in (rule.get('day') or (say('every day', 'كل يوم') if rule.get('start_hour') is not None else ''),
                                 f"{hours(rule['start_hour'])}–{hours(rule['end_hour'])}" if rule.get('start_hour') is not None else '') if x)
    kind = {'teaching_allowed': say('required teaching window', 'وقت التدريس الإلزامي'), 'teaching_preferred': say('preferred teaching window', 'وقت التدريس المفضل'), 'lecture_before_tutorial': say('lectures before tutorials', 'المحاضرات قبل التمارين'), 'unavailable': say('unavailable', 'غير متاح'), 'room_unavailable': say('closed', 'مغلقة'), 'group_unavailable': say('no classes', 'بدون محاضرات'),
            'preferred_period': say('prefers', 'يفضل'), 'group_allowed': say('only', 'فقط'), 'activity_allowed': say('only', 'فقط'), 'activity_room': say('room set', 'قاعة محددة'),
            'activities_not_same_day': say('not on the same day', 'ليست في نفس اليوم'), 'instructor_max_daily_hours': say('daily hours limit', 'حد ساعات يومي'),
            'group_max_daily_hours': say('daily hours limit', 'حد ساعات يومي'), 'instructor_max_days': say('teaching days limit', 'حد أيام التدريس')}.get(rule.get('type'), rule.get('type'))
    strength = say('required', 'إلزامي') if rule.get('strength') == 'mandatory' else say('preferred', 'مفضل')
    return ' · '.join(x for x in (who, kind, when, strength) if x)


TO_SPLIT = r'\s(?:to|into|الى|إلى|لـ|ليوم)\s'


def split_move(raw):
    """'Move X of G7 from Wed 8:30 to Mon 10:15' -> ('Move X of G7 from Wed 8:30', 'Mon 10:15')."""
    parts = re.split(TO_SPLIT, ' ' + raw.strip() + ' ', maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else '')


def free_slots(session, view, limit=6):
    """Times this session could move to with its groups, instructor and room all free (one per day first)."""
    from app.calendar_slots import day_placements
    duration = session['end_minute'] - session['start_minute']
    others = [s for s in view['sessions'] if (s['activity_id'], s['occurrence']) != (session['activity_id'], session['occurrence'])]
    groups = set(session['groups'])
    found = []
    for day in view['calendar']['days']:
        for start, end, _ in day_placements(view['calendar'], duration):
            if (day, start) == (session['day'], session['start_minute']):
                continue
            busy = any(s['day'] == day and s['start_minute'] < end and start < s['end_minute'] and
                       (groups & set(s['groups']) or s.get('instructor_id') == session.get('instructor_id') or s.get('room_id') == session.get('room_id')) for s in others)
            if not busy:
                found.append((day, start))
    by_day = []
    for day in view['calendar']['days']:  # spread the suggestions over the week
        by_day += [f for f in found if f[0] == day][:1]
    return (by_day + [f for f in found if f not in by_day])[:limit]


def ordinal_of(text):
    """0 for "first slot", 1 for "second…", -1 for "last…"; None when no ordinal is said."""
    from app.assistant import ORDINALS
    if re.search(r'(?<![\w])(last|اخر|الاخيره|الاخيرة)(?![\w])', text):
        return -1
    words = '|'.join(sorted(map(re.escape, ORDINALS), key=len, reverse=True))
    m = re.search(rf'(?<![\w])({words})(?![\w])', text)
    return ORDINALS[m.group(1)] - 1 if m else None


def finish_move(session, slots, view, need_target):
    """(change, problem) for a found session: where it goes, from the message's target."""
    from app.assistant import ARABIC_DIGITS, days_in, window
    if not need_target:
        return None, None
    target = normalise(slots.get('target') or '').translate(ARABIC_DIGITS)
    to_days = [d for d in days_in(target, view['calendar']) if d]
    to_span = window(target, view['calendar'], bare_period=True)
    room, _ = find_records(target, view['records'], 'rooms')
    if not to_days and not to_span and not room:
        return None, 'target'
    change = {}
    if to_days or to_span:
        change['day'] = to_days[0] if to_days else session['day']
        change['start_minute'] = to_span[0] if to_span else session['start_minute']
    if room:
        change['room_id'] = room[0]['id']
    return change, None


def find_session(slots, view, need_target):
    """The session a move/lock names, and for a move where it goes: (session, change, problem).

    Narrowed by what the message says (course, group, day, time), then by the group on screen or the
    one the chat was talking about, when that still leaves a match."""
    from app.assistant import ARABIC_DIGITS, days_in, window, find_group, find_programme, find_year
    source = normalise(slots.get('source') or '').translate(ARABIC_DIGITS)
    target = normalise(slots.get('target') or '').translate(ARABIC_DIGITS)
    courses = {r['id'] for _, r in named(source, view, ('courses',))}
    by_place = not courses  # "move the first slot on Monday": the session there, in the group being looked at
    groups = find_group(source, view['records'], find_programme(source, view['records']), find_year(source))
    days = [d for d in days_in(source, view['calendar']) if d]
    span = window(source, view['calendar'])
    names = {r['id']: r['data'] for r in view['records']}
    titles = {names[c]['name'] for c in courses if c in names}
    exact = {c for c in courses if names.get(c, {}).get('code') and mentions(source, normalise(names[c]['code']))}
    if by_place and not days and not span:
        return None, None, 'none'  # neither a course nor a day or period: nothing picks a session
    matches = list(view['sessions']) if by_place else \
        [s for s in view['sessions'] if (s['activity_id'] in exact) if exact] or \
        [s for s in view['sessions'] if s['activity_id'] in courses or names.get(s['activity_id'], {}).get('name') in titles]
    if groups:
        matches = [s for s in matches if groups[0]['id'] in s['groups']]
    elif by_place:
        # By day and period: only the group being looked at (on screen, or what the chat is about).
        context = [g for g in [(view.get('screen') or {}).get('group'), *((view.get('memory') or {}).get('groups') or [])] if g]
        if not context:
            return None, None, 'which_group'
        matches = [s for s in matches if context[0] in s['groups']]
    kind = next((k for k, w in (('lecture', ('lecture', 'محاضرة')), ('tutorial', ('tutorial', 'section', 'سكشن', 'سيكشن')), ('lab', ('lab', 'معمل'))) if H(source, w)), None)
    if kind:
        matches = [s for s in matches if s['type'] == kind] or matches
    if days:
        matches = [s for s in matches if s['day'] in days]
    if span:
        at_period = [s for s in matches if s['start_minute'] < span[1] and span[0] < s['end_minute']]
        if not at_period and by_place and days and len({s['day'] for s in matches}) and ordinal_of(source) is not None:
            # "The first slot on Monday" with nothing in period 1: the group's first class that day.
            n = ordinal_of(source)
            that_day = sorted((s for s in matches if s['day'] in days and (not groups or groups[0]['id'] in s['groups'])), key=lambda s: s['start_minute'])
            context = [g for g in [(view.get('screen') or {}).get('group'), *((view.get('memory') or {}).get('groups') or [])] if g]
            if not groups and context:
                that_day = [s for s in that_day if context[0] in s['groups']]
            if that_day and -len(that_day) <= n < len(that_day):
                return {**that_day[n], '_relative': n}, *finish_move(that_day[n], slots, view, need_target)
        matches = at_period
    if len(matches) > 1 and not groups:
        context = [g for g in [(view.get('screen') or {}).get('group'), *((view.get('memory') or {}).get('groups') or [])] if g]
        if by_place and not context:
            return None, None, 'which_group'
        for g in context:
            narrowed = [s for s in matches if g in s['groups']]
            if narrowed or by_place:  # by place, only that group's sessions count
                matches = narrowed
                break
    if len(matches) > 1 and not days:
        # The day the chat was just talking about ("What does BA5-G7 have on Wednesday?" then "move Management Accounting").
        said = set((view.get('memory') or {}).get('days') or [])
        narrowed = [s for s in matches if s['day'] in said]
        if narrowed:
            matches = narrowed
    if not matches:
        return None, None, 'none'
    if len(matches) > 1:
        return matches, None, 'many'
    if not need_target:
        return matches[0], None, None
    to_days = [d for d in days_in(target, view['calendar']) if d]
    to_span = window(target, view['calendar'], bare_period=True)  # "to third on Sunday": the third period
    room, _ = find_records(target, view['records'], 'rooms')
    if not to_days and not to_span and not room:
        return matches[0], None, 'target'
    change = {}
    if to_days or to_span:
        change['day'] = to_days[0] if to_days else matches[0]['day']
        change['start_minute'] = to_span[0] if to_span else matches[0]['start_minute']
    if room:
        change['room_id'] = room[0]['id']
    return matches[0], change, None


def answer_task(meaning, view, ar, say_fn):
    say = lambda en, a: say_fn(ar, en, a)
    intent, slots = meaning['intent'], meaning['slots']
    run = view.get('run')
    from app.assistant import describe, clock, AR_DAYS
    if intent == 'show_run':
        meant = view.get('meant')
        if meant and meant['status'] in ('queued', 'running'):
            return {'text': [say(f"{meant.get('name') or 'The timetable'} is still being generated; I opened it so you can watch.",
                                 f"{meant.get('name') or 'الجدول'} ما زال قيد الإنشاء؛ فتحته لتتابعه.")],
                    'action': {'type': 'open', 'page': 'timetable', 'run_id': meant['id'], 'label': say('Open it', 'فتحه')}, 'auto_open': True}
        if not run:
            return {'text': [say('There is no completed, valid teaching timetable yet. Ask me to generate one.', 'لا يوجد جدول مكتمل وصالح بعد. اطلب مني إنشاء جدول.')]}
        what = say('The timetable we generated in this chat', 'الجدول الذي أنشأناه في هذه المحادثة') if run.get('talked_about') else \
            say('The timetable on your screen', 'الجدول المعروض أمامك') if run.get('on_screen') else \
            say('The published timetable', 'الجدول المنشور') if run['published'] else say('The newest draft', 'أحدث مسودة')
        state = say('published', 'منشور') if run['published'] else say('not published', 'غير منشور')
        return {'text': [say(f"{what}: {run['sessions']} sessions, {state}{', inputs changed since' if run['stale'] else ''}. I opened it on the Timetable page.",
                             f"{what}: {run['sessions']} محاضرة، {state}{'، تغيرت المدخلات بعده' if run['stale'] else ''}. فتحته في صفحة الجدول.")],
                'action': {'type': 'open', 'page': 'timetable', 'run_id': run['id'], 'label': say('Open it', 'فتحه')}, 'auto_open': True}
    if intent == 'open_page':
        page = slots['page']
        why = {'file': say('Importing reads a spreadsheet you choose, so it happens on the Import page. I opened it.', 'الاستيراد يقرأ ملفاً تختاره، لذلك يتم من صفحة الاستيراد. فتحتها لك.'),
               'settings': say('Teaching days, periods, breaks and semester dates are set in Semester settings. I opened it.', 'أيام الدراسة والفترات والاستراحات وتواريخ الفصل تُضبط في إعدادات الفصل. فتحتها لك.'),
               'advising': say('Advising students (with their own course changes) are managed in Advising students. I opened it.', 'طلاب الإرشاد وتعديلات مقرراتهم تُدار من صفحة طلاب الإرشاد. فتحتها لك.')}.get(slots.get('why'))
        return {'text': [why or say(f'Opening {PAGE_NAMES[page][0]}.', f'جارٍ فتح {PAGE_NAMES[page][1]}.')],
                'action': {'type': 'open', 'page': page, 'label': say(f'Open {PAGE_NAMES[page][0]}', f'فتح {PAGE_NAMES[page][1]}')}, 'auto_open': True}
    if intent == 'cancel_run':
        last = view.get('last_status')
        if not last or last['status'] not in ('queued', 'running'):
            return {'text': [say('Nothing is being generated right now.', 'لا يوجد إنشاء جارٍ الآن.')]}
        return {'text': [say('Stop the timetable that is being generated now? Nothing else changes.', 'إيقاف الجدول الجاري إنشاؤه الآن؟ لا يتغير شيء آخر.')],
                'action': {'type': 'cancel_run', 'run_id': last['id'], 'label': say('Stop it', 'إيقاف')}}
    if intent == 'rename_run':
        name = slots['name'][:100]
        if slots.get('exams'):
            e = view.get('exam_run')
            if not e:
                return {'text': [say('There is no exam timetable to rename.', 'لا يوجد جدول امتحانات لإعادة تسميته.')]}
            return {'text': [say(f'Rename the latest exam timetable to "{name}"?', f'إعادة تسمية آخر جدول امتحانات إلى "{name}"؟')],
                    'action': {'type': 'rename_run', 'what': 'exams', 'run_id': e['id'], 'name': name, 'label': say('Rename', 'إعادة التسمية')}}
        if not run:
            return {'text': [say('There is no timetable to rename.', 'لا يوجد جدول لإعادة تسميته.')]}
        which = say('the timetable on your screen', 'الجدول المعروض أمامك') if run.get('on_screen') else say('the latest valid timetable', 'أحدث جدول صالح')
        return {'text': [say(f'Rename {which} to "{name}"?', f'إعادة تسمية {which} إلى "{name}"؟')],
                'action': {'type': 'rename_run', 'what': 'teaching', 'run_id': run['id'], 'name': name, 'label': say('Rename', 'إعادة التسمية')}}
    if intent == 'statistics':
        if not run or not view.get('stats'):
            return {'text': [say('There is no valid timetable to report on yet.', 'لا يوجد جدول صالح لعمل تقرير عنه بعد.')]}
        s = view['stats']
        cov, pref, use = s['coverage'], s['preferences'], s['utilization']
        lines = [say(f"Sessions scheduled: {cov['scheduled_sessions']} of {cov['expected_sessions']} ({cov['assignment_percent']}%).",
                     f"المحاضرات المجدولة: {cov['scheduled_sessions']} من {cov['expected_sessions']} ({cov['assignment_percent']}%).")]
        if pref['applicable_sessions']:
            lines.append(say(f"Preferences met: {pref['satisfaction_percent']}% of {pref['applicable_sessions']} sessions they apply to.",
                             f"التفضيلات المحققة: {pref['satisfaction_percent']}% من {pref['applicable_sessions']} محاضرة."))
        lines.append(say(f"Rooms used: {use['rooms_used']} of {use['rooms_total']}; instructors teaching: {use['instructors_used']} of {use['instructors_total']}.",
                         f"القاعات المستخدمة: {use['rooms_used']} من {use['rooms_total']}؛ المحاضرون: {use['instructors_used']} من {use['instructors_total']}."))
        lines.append(say(f"Checks: {'all passed' if s['validation']['passed'] else 'not all passed'}.", f"الفحوص: {'كلها ناجحة' if s['validation']['passed'] else 'ليست كلها ناجحة'}."))
        seen = view.get('screen') or {}
        q = '&'.join(f'{k}={v}' for k, v in (('group', seen.get('group')), ('year', seen.get('year')), ('major', seen.get('major'))) if v and run.get('on_screen'))
        return {'text': lines, 'action': {'type': 'download', 'url': f"/api/schedules/{run['id']}/statistics?format=pdf" + (f'&{q}' if q else ''),
                                          'label': say('Download the full report (PDF)', 'تحميل التقرير الكامل PDF')}}
    if intent == 'export_csv':
        if slots.get('exams'):
            e = view.get('exam_run')
            return {'text': [say('Here is the exam timetable as a spreadsheet.', 'هذا جدول الامتحانات كملف جدول بيانات.')],
                    'action': {'type': 'download', 'url': f"/api/exam-schedules/{e['id']}/export", 'label': say('Download CSV', 'تحميل CSV')}} if e else \
                {'text': [say('There is no exam timetable yet.', 'لا يوجد جدول امتحانات بعد.')]}
        if not run:
            return {'text': [say('There is no valid timetable to export yet.', 'لا يوجد جدول صالح للتصدير بعد.')]}
        return {'text': [say('Here is the timetable as a CSV spreadsheet (opens in Excel).', 'هذا الجدول كملف CSV (يفتح في Excel).')],
                'action': {'type': 'download', 'url': f"/api/schedules/{run['id']}/export.csv", 'label': say('Download CSV', 'تحميل CSV')}}
    if intent == 'input_checks':
        checks = view.get('checks') or {}
        blockers, warnings = checks.get('blockers', []), checks.get('warnings', [])
        key = 'message_ar' if ar else 'message'
        if not blockers:
            lines = [say('Yes: nothing blocks generation.', 'نعم: لا شيء يمنع الإنشاء.')]
            if warnings:
                lines.append(say(f'{len(warnings)} warnings to look at:', f'{len(warnings)} تنبيهات للمراجعة:'))
                lines += ['• ' + (w.get(key) or w.get('message', '')) for w in warnings[:6]]
            return {'text': lines, 'choices': [{'label': say('Generate the whole university', 'إنشاء جدول الجامعة كلها'), 'text': 'generate the whole university timetable'}]}
        return {'text': [say(f'{len(blockers)} problems block generation:', f'{len(blockers)} مشكلة تمنع الإنشاء:')] + ['• ' + (b.get(key) or b.get('message', '')) for b in blockers[:8]]
                + ([say(f'… and {len(blockers) - 8} more on the Timetable page.', f'… و{len(blockers) - 8} أخرى في صفحة الجدول.')] if len(blockers) > 8 else []),
                'action': {'type': 'open', 'page': 'timetable', 'label': say('Open Timetable', 'فتح الجدول')}}
    if intent == 'exam_pdf':
        e = view.get('exam_run')
        if not e:
            return {'text': [say('There is no exam timetable yet.', 'لا يوجد جدول امتحانات بعد.')]}
        if e.get('status') and e['status'] != 'completed':
            return {'text': [say('This exam attempt did not produce a complete timetable, so there is no PDF to save.', 'لم تُنتج محاولة الامتحانات هذه جدولًا كاملًا، لذلك لا يوجد ملف PDF للحفظ.')]}
        label = e.get('name') or ' '.join(str(value) for value in (e.get('kind'), e.get('start_date'), e.get('end_date')) if value)
        return {'text': [say(f'Here is the PDF for this exam timetable{": " + label if label else ""}.', f'هذا ملف PDF لجدول الامتحانات هذا{": " + label if label else ""}.')],
                'action': {'type': 'download', 'url': f"/api/exam-schedules/{e['id']}/exams.pdf" + ('?q=' + quote((view.get('screen') or {}).get('query') or '') if (view.get('screen') or {}).get('page') == 'exams' and (view.get('screen') or {}).get('query') else ''), 'label': say('Download PDF', 'تحميل PDF')}}
    if intent == 'exam_when':
        exams = view.get('exams') or []
        names = {r['id']: r['data'] for r in view['records']}
        # Activities point at their catalogue course; exams are per catalogue course.
        catalogue = {names[c].get('course_id') for c in slots['courses'] if c in names} - {None}
        titles = {names[c].get('name') for c in slots['courses'] if c in names}
        rows = [x for x in exams if x.get('course_id') in catalogue or x.get('course_name') in titles]
        if slots.get('exam_kind'):
            kinds = {slots['exam_kind'], 'makeup'} if slots['exam_kind'] == 'midterm' else {slots['exam_kind']}
            rows = [x for x in rows if x.get('exam_type', 'midterm') in kinds]  # timetables made before exam types were all midterms
        if not rows:
            return {'text': [say('I could not find that exam in the latest exam timetable.', 'لم أجد هذا الامتحان في آخر جدول امتحانات.')]}
        return {'text': [say('From the latest exam timetable:', 'من آخر جدول امتحانات:')] +
                [f"• {x.get('label') or {'final': say('Final', 'نهائي'), 'makeup': say('Second-chance midterm', 'فرصة ثانية'), 'quiz': say('Quiz', 'اختبار قصير')}.get(x.get('exam_type'), say('Midterm', 'منتصف الفصل'))} · {x['course_name']} · {x['date']} {x['start_time']}–{x.get('end_time', '')}"
                 + (f" · {', '.join(h['room_code'] for h in x.get('halls') or [])}" if x.get('halls') else '') for x in sorted(rows, key=lambda x: (x['date'], x['start_time']))[:10]]}
    if intent in ('move_session', 'lock_session'):
        if not run:
            return {'text': [say('There is no valid timetable to change yet.', 'لا يوجد جدول صالح لتعديله بعد.')]}
        session, change, problem = find_session(slots, view, intent == 'move_session')
        if problem == 'which_group':
            return {'text': [say("Whose timetable? Name the group (for example \"move BA5-G7's first slot on Monday to the third on Sunday\"), or filter the Timetable page to it.",
                                 'جدول أي مجموعة؟ اذكر المجموعة أو اعرضها في صفحة الجدول.')], 'asking': True}
        if problem == 'none' and intent == 'lock_session' and not named(normalise(slots.get('source') or ''), view, ('courses',)):
            return {'text': [say('Only a session can be locked in place. Which one? Name the course and the group or day (for example "lock Math I of INF1-G7 on Sunday").',
                                 'يمكن تثبيت محاضرة فقط. أيها؟ اذكر المقرر والمجموعة أو اليوم (مثلاً "ثبت Math I لـ INF1-G7 يوم الأحد").')], 'asking': True}
        if problem == 'none' and not named(normalise(slots.get('source') or ''), view, ('courses',)):
            return {'text': [say('There is no session there in this timetable (for the group being looked at). Check the day and period, or name the course.',
                                 'لا توجد محاضرة في هذا المكان في هذا الجدول (للمجموعة المعروضة). راجع اليوم والفترة أو اذكر المقرر.')], 'asking': True}
        if problem == 'none':
            return {'text': [say('I could not find that session in this timetable. Name the course and the group or day.',
                                 'لم أجد هذه المحاضرة في هذا الجدول. اذكر المقرر والمجموعة أو اليوم.')], 'asking': True}
        if problem == 'many':
            return {'text': [say(f'{len(session)} sessions match. Which one?', f'{len(session)} محاضرات مطابقة. أيها؟')],
                    'choices': [{'label': f"{s['code']} · {(AR_DAYS.get(s['day'], s['day']) if ar else s['day'])} {clock(s['start_minute'])} · {s['room']}",
                                 'text': f"{s['code']} on {s['day']} {clock(s['start_minute'])}"} for s in session[:10]], 'asking': True}
        if problem == 'target':
            free = working_moves(view, session)
            return {'text': [say(f"Where should {session['course']} ({session['code']}, {session['day']} {clock(session['start_minute'])}) go? These times work (checked against everyone's timetable and the rules):",
                                 f"إلى أين تُنقل {session['course']} ({session['code']}، {AR_DAYS.get(session['day'], session['day'])} {clock(session['start_minute'])})؟ هذه الأوقات تصلح (مفحوصة مقابل جداول الجميع والقيود):")]
                    + ([] if free else [say('No free time keeps all three free; name a day, time or another room.', 'لا يوجد وقت يناسب الثلاثة؛ اذكر يوماً أو وقتاً أو قاعة أخرى.')]),
                    'choices': [{'label': f"{(AR_DAYS.get(d, d) if ar else d)} {clock(m)}", 'text': f"to {d} {clock(m)}"} for d, m in free], 'asking': True}
        if intent == 'lock_session':
            return {'text': [say(f"Lock {session['course']} ({session['code']}) on {session['day']} {clock(session['start_minute'])}, room {session['room']}, {session['instructor']}? Future timetables keep it there.",
                                 f"تثبيت {session['course']} ({session['code']}) يوم {AR_DAYS.get(session['day'], session['day'])} {clock(session['start_minute'])}، قاعة {session['room']}، {session['instructor']}؟ تبقى ثابتة في الجداول القادمة.")],
                    'action': {'type': 'lock_session', 'run_id': run['id'], 'activity_id': session['activity_id'], 'occurrence': session['occurrence'], 'label': say('Lock it', 'تثبيت')}}
        rooms = {r['id']: r['data'].get('code') for r in view['records'] if r['kind'] == 'rooms'}
        lead = []
        if session.get('_relative') is not None:
            which = {0: say('first', 'أول'), 1: say('second', 'ثاني'), 2: say('third', 'ثالث'), -1: say('last', 'آخر')}.get(session['_relative'], str(session['_relative'] + 1))
            lead = [say(f"That period is empty, so I took the {which} class of the day: {session['course']} at {clock(session['start_minute'])}.",
                        f"هذه الفترة فارغة، فأخذت {which} محاضرة في اليوم: {session['course']} الساعة {clock(session['start_minute'])}.")]
        report = try_move(view, session, change)
        if report is not None and not report['passed']:
            # Say exactly what clashes, and offer what works instead: another room at that time, or other times.
            reasons = why_not(report, view, session, say)
            when = f"{(AR_DAYS.get(change['day'], change['day']) if ar else change['day'])} {clock(change['start_minute'])}" if 'day' in change else ''
            room = working_room(view, session, change) if 'day' in change and not change.get('room_id') else None
            times = working_moves(view, session)
            choices = ([{'label': say(f"{when} in room {room['data']['code']}", f"{when} في قاعة {room['data']['code']}"),
                         'text': f"to {change['day']} {clock(change['start_minute'])} in room {room['data']['code']}"}] if room else []) + \
                      [{'label': f"{(AR_DAYS.get(d, d) if ar else d)} {clock(m)}", 'text': f"to {d} {clock(m)}"} for d, m in times]
            codes = {r['id']: r['data'].get('code') for r in view['records'] if r['kind'] == 'groups'}
            members = [codes.get(g, '?') for g in session.get('groups', [])]
            sharing = [say(f"{session['code']} is one {session.get('type') or 'session'} shared by {len(members)} groups ({', '.join(members[:8])}{'…' if len(members) > 8 else ''}). "
                           f"Moving it moves it for all of them, so it can only go where every one of them is free.",
                           f"{session['code']} حصة واحدة مشتركة بين {len(members)} مجموعات ({'، '.join(members[:8])}). نقلها ينقلها للجميع، لذلك تُنقل فقط لوقت يكونون كلهم متاحين فيه.")] if len(members) > 1 else []
            if slots.get('explain') and sharing:
                # Answer the question: it isn't only this group's class.
                busy = [codes.get(rid) for v in report.get('violations') or [] for rid in v.get('resource_ids') or [] if rid in session.get('groups', [])]
                busy = list(dict.fromkeys(b for b in busy if b))
                return {'text': [say('Because they are in the same class. ', 'لأنهم في نفس المحاضرة. ') + sharing[0],
                                 say(f"{', '.join(busy)} attend{'s' if len(busy) == 1 else ''} it too, and already {'has' if len(busy) == 1 else 'have'} another class at {when}, so the lecture can't go there."
                                     if busy else f"At {when} someone who attends it is busy, so the lecture can't go there.",
                                     f"{'، '.join(busy)} تحضر هذه المحاضرة أيضاً ولديها محاضرة أخرى في {when}، لذلك لا يمكن نقلها هناك."),
                                 say("If this group should have its own lecture instead, that needs a separate lecture section in Course setup.",
                                     'إذا كانت هذه المجموعة تحتاج محاضرة خاصة بها، فذلك يحتاج شعبة محاضرة منفصلة في إعداد المقررات.'),
                                 say('Times that work for all of them:' if choices else 'No time works for all of them right now.', 'أوقات تناسبهم جميعاً:' if choices else 'لا يوجد وقت يناسبهم جميعاً الآن.')],
                        'choices': choices, 'asking': True}
            return {'text': lead + sharing + [say(f"{session['course']} ({session['code']}) can't move to {when}:", f"لا يمكن نقل {session['course']} ({session['code']}) إلى {when}:")]
                    + ['• ' + r for r in reasons]
                    + [say('These work instead:' if choices else 'No other time keeps everyone free; try another week day, or change a rule.',
                           'هذه تصلح بدلاً من ذلك:' if choices else 'لا يوجد وقت آخر يناسب الجميع؛ جرّب يوماً آخر أو عدّل قيداً.')],
                    'choices': choices, 'asking': True}
        to = ' · '.join(x for x in ((AR_DAYS.get(change['day'], change['day']) if ar else change['day']) + ' ' + clock(change['start_minute']) if 'day' in change else '',
                                    say('room ', 'قاعة ') + rooms.get(change['room_id'], '') if change.get('room_id') else '') if x)
        return {'text': lead + [say(f"Move {session['course']} ({session['code']}) from {session['day']} {clock(session['start_minute'])} to {to}? This makes a new draft and checks it; the original stays as it is.",
                             f"نقل {session['course']} ({session['code']}) من {AR_DAYS.get(session['day'], session['day'])} {clock(session['start_minute'])} إلى {to}؟ يُنشئ ذلك مسودة جديدة ويفحصها؛ تبقى الأصلية كما هي.")],
                'action': {'type': 'move_session', 'run_id': run['id'], 'change': {'activity_id': session['activity_id'], 'occurrence': session['occurrence'], **change}, 'label': say('Move it', 'نقل')}}
    if intent == 'create_account':
        step = account_step(slots, view, say)
        return step
    if intent == 'reset_account':
        text = normalise(slots['raw'])
        users = view.get('users', [])
        email = EMAIL.search(slots['raw'])
        hits = [u for u in users if email and u['email'] == email.group().lower().strip('.,')] or \
               [u for u in users if mentions(text, normalise(u['name'])) or (len(plain(u['name']).split()) and mentions(text, plain(u['name'])))]
        if len(hits) != 1:
            return {'text': [say('Whose account? Give their email or full name.' if not hits else f'{len(hits)} accounts match. Which one?',
                                 'حساب من؟ اذكر البريد أو الاسم الكامل.' if not hits else f'{len(hits)} حسابات مطابقة. أيها؟')],
                    'choices': [{'label': f"{u['name']} ({u['email']})", 'text': f"reset password for {u['email']}"} for u in hits[:6]], 'asking': bool(hits)}
        u = hits[0]
        return {'text': [say(f"Make a new setup link for {u['name']} ({u['email']})? Their current sessions are signed out; the link expires in 30 minutes.",
                             f"إنشاء رابط إعداد جديد لـ{u['name']} ({u['email']})؟ تُغلق جلساته الحالية؛ ينتهي الرابط بعد 30 دقيقة.")],
                'action': {'type': 'reset_account', 'user_id': u['id'], 'user_version': u['version'], 'label': say('Make the link', 'إنشاء الرابط')}}
    if intent == 'list_accounts':
        users = view.get('users', [])
        from collections import Counter
        counts = Counter(u['role'] for u in users if u['active'])
        return {'text': [say(f"{sum(counts.values())} active accounts: " + ', '.join(f'{n} {r}' for r, n in counts.most_common()), f"{sum(counts.values())} حساب نشط: " + '، '.join(f'{n} {r}' for r, n in counts.most_common()))],
                'action': {'type': 'open', 'page': 'accounts', 'label': say('Open Accounts', 'فتح الحسابات')}}
    if intent in ('list_rules', 'remove_rule', 'approve_rules'):
        rules = view.get('rules', [])
        about = set(slots.get('about') or [])
        mine = [r for r in rules if r['id'] in (slots.get('words') or '')] or \
            [r for r in rules if not about or about & {r.get('instructor_id'), r.get('room_id'), r.get('group_id'), r.get('activity_id')}]
        if intent == 'approve_rules':
            drafts = [r for r in rules if r['status'] == 'draft']
            if not drafts:
                return {'text': [say('There are no draft rules to approve.', 'لا توجد قيود مسودة للاعتماد.')]}
            return {'text': [say(f'Approve {len(drafts)} draft rules?', f'اعتماد {len(drafts)} قيود مسودة؟')] + ['• ' + rule_line(r, view, say) for r in drafts[:10]],
                    'action': {'type': 'approve_rules', 'rule_ids': [r['id'] for r in drafts], 'label': say('Approve all', 'اعتماد الكل')}}
        if intent == 'list_rules':
            if not mine:
                return {'text': [say('No rules found.' if about else 'There are no rules yet.', 'لا توجد قيود.')]}
            lines = [say(f'{len(mine)} rules ({sum(r["status"] == "approved" for r in mine)} approved):', f'{len(mine)} قيود ({sum(r["status"] == "approved" for r in mine)} معتمدة):')]
            lines += ['• ' + rule_line(r, view, say) + ('' if r['status'] == 'approved' else say(' · draft', ' · مسودة')) for r in mine[:15]]
            return {'text': lines, 'action': {'type': 'open', 'page': 'constraints', 'label': say('Open Constraints', 'فتح القيود')}}
        if len(mine) != 1:
            if not mine:
                return {'text': [say('Which rule? I could not find one matching that.', 'أي قيد؟ لم أجد قيداً مطابقاً.')], 'asking': True}
            return {'text': [say('Which rule should I remove?', 'أي قيد أحذف؟')],
                    'choices': [{'label': rule_line(r, view, say), 'text': f"remove rule {r['id']}"} for r in mine[:8]], 'asking': True}
        r = mine[0]
        return {'text': [say(f'Remove this rule? {rule_line(r, view, say)}. Future timetables will no longer follow it.', f'حذف هذا القيد؟ {rule_line(r, view, say)}. لن تلتزم به الجداول القادمة.')],
                'action': {'type': 'delete_rule', 'rule_id': r['id'], 'label': say('Remove it', 'حذف')}}
    if intent == 'add_rule':
        out = parse(slots['raw'], {'records': view['records'], 'calendar': view['calendar']})
        rules = [p['data'] for p in out.get('proposals', []) if p.get('kind') == 'rule']
        if out.get('decision') == 'ready' and rules:
            return {'text': [say('I read this as:', 'فهمت هذا كالتالي:')] + ['• ' + rule_line(r, view, say) for r in rules]
                    + [say('Add and approve it? Future timetables will follow it.', 'إضافته واعتماده؟ ستلتزم به الجداول القادمة.')],
                    'action': {'type': 'add_rules', 'text': slots['raw'], 'count': len(rules), 'label': say('Add and approve', 'إضافة واعتماد')}}
        asks = [c.replace('_', ' ') for c in out.get('clarifications', [])] + [c.replace('_', ' ') for c in out.get('unsupported', [])]
        return {'text': [say("I need a bit more to turn that into a rule: ", 'أحتاج تفاصيل أكثر لتحويله إلى قيد: ') + ', '.join(asks) + '.',
                         say('Say it again with the person, room or group, the day and the time (for example "Dr. Ahmed can\'t teach Sunday before 10:30").',
                             'أعد صياغته مع الشخص أو القاعة أو المجموعة واليوم والوقت (مثلاً "د. أحمد مش متاح الأحد قبل 10:30").')]}
    if intent == 'delete_record':
        targets = slots['targets']
        if len(targets) > 1:
            return {'text': [say('Which one should I delete?', 'أيها أحذف؟')],
                    'choices': [{'label': f"{k[:-1]} {view_record(view, i).get('code') or view_record(view, i).get('name')}", 'text': f"delete {view_record(view, i).get('code') or view_record(view, i).get('name')}"} for k, i in targets], 'asking': True}
        kind, ident = targets[0]
        data = view_record(view, ident)
        label = data.get('code') if kind in ('rooms', 'groups', 'courses') else data.get('name')
        what = {'rooms': say('room', 'القاعة'), 'instructors': say('instructor', 'المحاضر'), 'groups': say('group', 'المجموعة'), 'courses': say('course activity', 'نشاط المقرر')}[kind]
        return {'text': [say(f"Delete the {what} {label}? This can't be undone. It is refused if a course, rule or account still uses it.",
                             f"حذف {what} {label}؟ لا يمكن التراجع. يُرفض إذا كان مقرر أو قيد أو حساب ما زال يستخدمه.")],
                'action': {'type': 'delete_record', 'kind': kind, 'id': ident, 'label': say('Delete', 'حذف')}}
    if intent == 'edit_record':
        return edit_step(slots, view, ar, say)
    if intent == 'programme_info':
        return programme_info(slots, view, say)
    if intent == 'record_info':
        lines = []
        for kind, ident in slots['targets']:
            d = view_record(view, ident)
            if kind == 'groups':
                courses = sum(ident in r['data'].get('group_ids', []) for r in view['records'] if r['kind'] == 'courses')
                lines.append(say(f"{d.get('code')}: {d.get('size')} students · {d.get('major')} year {d.get('year')} · in {courses} course activities",
                                 f"{d.get('code')}: {d.get('size')} طالب · {d.get('major')} سنة {d.get('year')} · في {courses} نشاط مقرر"))
            elif kind == 'rooms':
                lines.append(say(f"{d.get('code')}: {d.get('capacity')} seats · {', '.join(d.get('room_types') or [d.get('room_type') or '?'])}"
                                 + (f" · reserved for {', '.join(d['reserved_majors'])}" if d.get('reserved_majors') else ''),
                                 f"{d.get('code')}: {d.get('capacity')} مقعد · {', '.join(d.get('room_types') or [d.get('room_type') or '?'])}"))
            else:
                role = {'doctor': say('doctor', 'دكتور'), 'ta': say('TA', 'معيد')}.get(d.get('position'), say('position not set', 'الوظيفة غير محددة'))
                lines.append(say(f"{d.get('name')} ({d.get('code')}): {role} · {d.get('department')} · day off {d.get('day_off') or 'none'}",
                                 f"{d.get('name')} ({d.get('code')}): {role} · {d.get('department')} · يوم الإجازة {d.get('day_off') or 'لا يوجد'}"))
        return {'text': lines}
    return None


def view_record(view, ident):
    return next((r['data'] for r in view['records'] if r['id'] == ident), {})


def edit_step(slots, view, ar, say):
    from app.assistant import ARABIC_DIGITS, days_in
    kind, ident = slots['targets'][0]
    data = dict(view_record(view, ident))
    raw = slots['raw']
    text = normalise(raw).translate(ARABIC_DIGITS)
    after = re.split(r'\s(?:to|into|=|الى|إلى|ل)\s', text, maxsplit=1)
    value = after[1] if len(after) > 1 else ''
    number = re.search(r'(\d{1,4})(?!.*\d)', value or text)
    changed = []
    if kind == 'rooms':
        if number and H(text, ('capacity', 'seats', 'size', 'سعة', 'مقعد', 'كراسي')):
            data['capacity'] = int(number.group(1)); changed.append(say(f'capacity {data["capacity"]}', f'السعة {data["capacity"]}'))
        types = [t for t, w in (('lab', ('lab', 'معمل')), ('lecture', ('lecture', 'محاضرات')), ('flexible', ('flexible', 'either', 'both', 'الاثنين')), ('exam_hall', ('exam', 'امتحان'))) if H(value, w)]
        if types and H(text, ('type', 'use', 'used for', 'into a', 'نوع', 'تستخدم')):
            data['room_types'] = types; data['room_type'] = types[0]; changed.append(say(f'type {", ".join(types)}', f'النوع {", ".join(types)}'))
        if (m := re.search(r'(?:rename|code)\s.*?\sto\s+([\w.\-]+)', raw, re.I)):
            data['code'] = data['name'] = m.group(1).upper(); changed.append(say(f'code {data["code"]}', f'الرمز {data["code"]}'))
    if kind == 'groups' and number and H(text, ('size', 'students', 'عدد', 'طلاب', 'طالب')):
        data['size'] = int(number.group(1)); changed.append(say(f'size {data["size"]}', f'العدد {data["size"]}'))
    if kind == 'instructors':
        if H(text, ('day off', 'off day', 'اجازة', 'إجازة', 'اجازته', 'اجازتها')):
            day = [d for d in days_in(value or text, view['calendar']) if d]
            if day or H(value, ('none', 'no ', 'nothing', 'مفيش', 'لا يوجد', 'بدون')):
                data['day_off'] = day[0] if day else None; changed.append(say(f"day off {data['day_off'] or 'none'}", f"يوم الإجازة {data['day_off'] or 'لا يوجد'}"))
        if H(value, ('ta', 'teaching assistant', 'معيد')) and H(text, ('position', 'ta', 'doctor', 'معيد', 'دكتور')):
            data['position'] = 'ta'; changed.append(say('position TA', 'معيد'))
        elif H(value, ('doctor', 'دكتور')) and H(text, ('position', 'doctor', 'دكتور')):
            data['position'] = 'doctor'; changed.append(say('position doctor', 'دكتور'))
        if H(text, ('department', 'قسم')) and value:
            dept = re.split(r'\s(?:to|الى|إلى)\s', raw, maxsplit=1, flags=re.I)[-1].strip(' .')
            data['department'] = dept; changed.append(say(f'department {dept}', f'القسم {dept}'))
        if (m := re.search(r'rename\s.*?\sto\s+(.+)$', raw, re.I)):
            data['name'] = m.group(1).strip(' .'); changed.append(say(f'name {data["name"]}', f'الاسم {data["name"]}'))
    label = data.get('code') if kind != 'instructors' else view_record(view, ident).get('name')
    if not changed:
        fields = {'rooms': say('capacity, type (lecture/lab/exam) or code', 'السعة أو النوع أو الرمز'), 'groups': say('number of students', 'عدد الطلاب'),
                  'instructors': say('day off, position (doctor/TA), department or name', 'يوم الإجازة أو الوظيفة أو القسم أو الاسم')}[kind]
        return {'text': [say(f'What should change for {label}? I can change its {fields}. For example "set its capacity to 40".',
                             f'ما الذي يتغير في {label}؟ أستطيع تغيير {fields}. مثلاً "خلي السعة 40".')]}
    return {'text': [say(f"Change {label}: {', '.join(changed)}?", f"تعديل {label}: {'، '.join(changed)}؟")],
            'action': {'type': 'update_record', 'kind': kind, 'id': ident, 'body': {k: v for k, v in data.items() if k not in ('id', 'kind')}, 'label': say('Save', 'حفظ')}}


def try_move(view, session, change):
    """The real validator's verdict on this move, run on the timetable in use (the same check the server makes)."""
    from app.calendar_slots import end_for
    from app.validation import validate_schedule
    data = view.get('run_rows')
    if not data:
        return None
    snap, rows = data['snapshot'], [dict(a) for a in data['assignments']]
    activities = {r['id']: r for r in snap['records'] if r['kind'] == 'courses'}
    target = next((a for a in rows if (a['activity_id'], a['occurrence']) == (session['activity_id'], session['occurrence'])), None)
    if not target:
        return None
    if 'day' in change:
        end = end_for(snap['calendar'], activities[target['activity_id']]['duration'], change['start_minute'])
        if end is None:
            return {'passed': False, 'errors': ['not_a_teaching_period'], 'violations': []}
        target.update(day=change['day'], start_minute=change['start_minute'], end_minute=end)
    if change.get('room_id'):
        target['room_id'] = change['room_id']
    return validate_schedule(snap, rows)


def why_not(report, view, session, say):
    """The validator's reasons, in names: who or what is busy, with which session."""
    from app.assistant import clock
    names = {r['id']: (r['data'].get('code') if r['kind'] in ('rooms', 'groups', 'courses') else r['data'].get('name')) for r in view['records']}
    kinds = {r['id']: r['kind'] for r in view['records']}
    lines = []
    for v in report.get('violations') or []:
        if v['code'] == 'resource_conflicts':
            others = [s for s in v.get('sessions') or [] if (s.get('activity_id'), s.get('occurrence')) != (session['activity_id'], session['occurrence'])]
            other = others[0] if others else None
            for rid in v.get('resource_ids') or []:
                who = names.get(rid, rid)
                kind = {'groups': say('group', 'المجموعة'), 'rooms': say('room', 'القاعة'), 'instructors': say('instructor', 'المحاضر')}.get(kinds.get(rid), '')
                shared = rid in session.get('groups', []) and len(session.get('groups', [])) > 1
                if shared:
                    who = who + say(' (it attends this lecture too)', ' (تحضر هذه المحاضرة أيضاً)')
                if other:
                    lines.append(say(f"{kind} {who} already has {names.get(other['activity_id'], '?')} on {other['day']} {clock(other['start_minute'])}–{clock(other['end_minute'])}.",
                                     f"{kind} {who} لديه بالفعل {names.get(other['activity_id'], '?')} يوم {other['day']} {clock(other['start_minute'])}."))
                else:
                    lines.append(say(f"{kind} {who} is already busy then.", f"{kind} {who} مشغول في هذا الوقت."))
        elif v['code'] == 'advising_student_conflicts':
            lines.append(say('An advising student who takes this course has another of their courses at that time.', 'طالب إرشاد يدرس هذا المقرر لديه مقرر آخر في نفس الوقت.'))
        elif v['code'] == 'not_a_teaching_period':
            lines.append(say("That time isn't the start of a teaching period this session fits.", 'هذا الوقت ليس بداية فترة تدريس تناسب هذه الحصة.'))
        else:
            rules = {r['id']: r.get('title') for r in view.get('rules', [])}
            named = [rules[r] for r in v.get('rule_ids') or [] if rules.get(r)]
            lines.append(say(v.get('message', v['code']).replace('_', ' ').capitalize() + (f" ({', '.join(named)})" if named else '') + '.',
                             v.get('message', v['code']).replace('_', ' ') + (f" ({'، '.join(named)})" if named else '') + '.'))
    if not lines and report.get('errors'):
        lines = [say(', '.join(e.replace('_', ' ') for e in report['errors']).capitalize() + '.', '، '.join(report['errors']))]
    return list(dict.fromkeys(lines))[:6]


def working_moves(view, session, limit=5, budget=14):
    """Times this session can really move to (each checked by the validator), spread over the week."""
    candidates = free_slots(session, view, limit=40)
    good = []
    for day, start in candidates[:budget]:
        report = try_move(view, session, {'day': day, 'start_minute': start})
        if report is None:
            return candidates[:limit]  # no timetable rows to check against: the quick check only
        if report['passed']:
            good.append((day, start))
            if len(good) >= limit:
                break
    return good


def working_room(view, session, change):
    """At the asked time, another room of the right kind and size that makes the move pass."""
    records = {r['id']: r['data'] for r in view['records']}
    size = sum(records.get(g, {}).get('size') or 0 for g in session['groups'])
    kind = session.get('type')
    busy = {s.get('room_id') for s in view['sessions'] if s['day'] == change.get('day') and s['start_minute'] < change['start_minute'] + 90 and change['start_minute'] < s['end_minute']}
    rooms = sorted((r for r in view['records'] if r['kind'] == 'rooms' and r['id'] not in busy and (r['data'].get('capacity') or 0) >= size
                    and (kind in (r['data'].get('room_types') or [r['data'].get('room_type')]) or 'flexible' in (r['data'].get('room_types') or []))),
                   key=lambda r: r['data'].get('capacity') or 0)
    for room in rooms[:6]:
        report = try_move(view, session, {**change, 'room_id': room['id']})
        if report and report['passed']:
            return room
    return None


def programme_info(slots, view, say):
    """Which years a programme has (groups and students in each), which groups a year has, or all programmes."""
    from app.assistant import programmes
    groups = [r for r in view['records'] if r['kind'] == 'groups']
    by = {}
    for g in groups:
        by.setdefault(g['data'].get('major') or say('No programme', 'بدون برنامج'), {}).setdefault(g['data'].get('year'), []).append(g['data'])
    asked = slots.get('programmes') or []
    if slots.get('what') == 'programmes' or not asked:
        if slots.get('what') == 'years' and not asked:
            pass  # "what years are there?" without a programme: every programme's years
        lines = [say(f'{len(by)} programmes:', f'{len(by)} برامج:')]
        for p in sorted(by):
            years = sorted(y for y in by[p] if y)
            lines.append(f"• {p}: " + say(f"year{'s' if len(years) != 1 else ''} {', '.join(map(str, years)) or '—'}", f"سنة {'، '.join(map(str, years)) or '—'}")
                         + say(f" · {sum(len(v) for v in by[p].values())} groups", f" · {sum(len(v) for v in by[p].values())} مجموعة"))
        return {'text': lines}
    lines = []
    for p in asked:
        years = by.get(p, {})
        if slots.get('what') == 'groups':
            wanted = [slots['year']] if slots.get('year') else sorted(y for y in years if y)
            for y in wanted:
                codes = sorted((g['code'] for g in years.get(y, [])), key=lambda c: (len(c), c))
                lines.append(say(f"{p} year {y}: {len(codes)} groups", f"{p} سنة {y}: {len(codes)} مجموعة") + (': ' + ', '.join(codes) if codes else '.'))
            continue
        listed = sorted(y for y in years if y)
        lines.append(say(f"{p} has {len(listed)} study year{'s' if len(listed) != 1 else ''}:", f"{p} بها {len(listed)} سنة دراسية:"))
        for y in listed:
            rows = years[y]
            lines.append(say(f"• Year {y}: {len(rows)} groups, {sum(r.get('size') or 0 for r in rows)} students",
                             f"• سنة {y}: {len(rows)} مجموعة، {sum(r.get('size') or 0 for r in rows)} طالب"))
        if None in years:
            lines.append(say(f"• No year set: {len(years[None])} groups", f"• بدون سنة: {len(years[None])} مجموعة"))
    first = asked[0]
    choices = [{'label': say(f'Groups in year {y}', f'مجموعات سنة {y}'), 'text': f'which groups are in {first} year {y}'} for y in sorted(y for y in by.get(first, {}) if y)] \
        if slots.get('what') == 'years' else []
    return {'text': lines, 'choices': choices}
