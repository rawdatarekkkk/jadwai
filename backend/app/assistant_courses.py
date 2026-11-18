"""JAI creates courses and adds groups or instructors to them, the way Course setup does.

A course is a catalogue entry (name, code, the groups that take it, who may teach its lectures,
tutorials and labs) plus its teaching sessions: one lecture shared by its groups, and one tutorial
or lab per group, each 90 minutes once a week unless changed later in Course setup. JAI asks for
what the message leaves out, suggests instructors who already teach those groups, shows the whole
plan, and on confirm the browser saves it through /api/course-catalog and /api/records/courses.
"""
import re
from collections import Counter
from app.rule_parser import find_records, mentions, normalise

FIELDS = ('name', 'code', 'groups', 'kinds', 'lecture', 'tutorial', 'lab')
KINDS = {'lecture': ('lecture', 'lectures', 'محاضرة', 'محاضرات'), 'tutorial': ('tutorial', 'tutorials', 'section', 'سكشن', 'سكاشن', 'تمارين'),
         'lab': ('lab', 'labs', 'معمل', 'معامل')}
NONE = ('none', 'no', 'nobody', 'later', 'skip', 'not yet', 'لا', 'مفيش', 'بعدين')
POSITION = {'lecture': 'doctor', 'tutorial': 'ta', 'lab': 'ta'}


def H(text, words):
    return any(w in text for w in words)


def catalog_named(text, view):
    """Catalogue courses the text names by code or name."""
    return [c for c in view.get('catalog', []) if mentions(text, normalise(c['code'])) or mentions(text, normalise(c['name']))]


def groups_in(text, view, memory=None):
    """Groups the text names: codes ("IS3-G4, IS3-G5"), a programme and year ("all of IT Security year 3"), or "them"."""
    from app.assistant import find_programme, find_year, find_group
    records = view['records']
    found = [r for r in records if r['kind'] == 'groups' and mentions(text, normalise(r['data'].get('code', '')))]
    if not found:
        progs, year = find_programme(text, records), find_year(text)
        found = find_group(text, records, progs, year)
        if not found and progs and year:
            found = [r for r in records if r['kind'] == 'groups' and r['data'].get('major') in progs and r['data'].get('year') == year]
        if not found and len(progs) == 1 and not year and H(text, ('all', 'every', 'whole', 'كل', 'كلها')):
            found = [r for r in records if r['kind'] == 'groups' and r['data'].get('major') == progs[0]]
    return [g['id'] for g in found]


def people_in(text, view, kind):
    """Instructors named, and those of the wrong position for this kind of teaching."""
    rows = []
    for part in re.split(r',|\band\b|\bو\b|&', text):
        found, _ = find_records(normalise(part), view['records'], 'instructors')
        rows += [r for r in found if r not in rows]
    right = [r for r in rows if r['data'].get('position') in (POSITION[kind], None)]
    return [r['id'] for r in right], [r['data']['name'] for r in rows if r not in right]


def suggestions(view, groups, kind):
    """Instructors of the right position who already teach these groups (or their programme): the likely ones."""
    programmes = {r['data'].get('major') for r in view['records'] if r['id'] in groups}
    cohort = {r['id'] for r in view['records'] if r['kind'] == 'groups' and r['data'].get('major') in programmes}
    count = Counter(t for r in view['records'] if r['kind'] == 'courses' and set(r['data'].get('group_ids', [])) & cohort
                    for t in r['data'].get('eligible_instructors', []))
    people = {r['id']: r['data'] for r in view['records'] if r['kind'] == 'instructors'}
    return [people[t]['name'] for t, _ in count.most_common() if t in people and people[t].get('position') == POSITION[kind]][:6]


def first_fill(raw, text, view):
    form = {}
    name = re.search(r'(?:called|named|name is|اسمه|اسمها)\s+["“]?([^,"”]+?)["”]?(?:\s*[,(]|\s+(?:with|code|for|taught|كود|لـ)\s|$)', raw, re.I)
    if name:
        form['name'] = name.group(1).strip()
    code = re.search(r'(?:code|كود)\s*:?\s*([A-Za-z]{2,6}\s?\d{2,4}[A-Za-z]?)', raw, re.I)
    if code:
        form['code'] = code.group(1).replace(' ', '').upper()
    groups = groups_in(text, view)
    if groups and H(text, (' for ', ' to ', 'لـ', 'ل ')):
        form['groups'] = groups
    kinds = [k for k, w in KINDS.items() if H(text, w)]
    if kinds:
        form['kinds'] = kinds
    return form


def answer_field(field, raw, text, view, form):
    raw = raw.strip()
    if field == 'name':
        return raw.strip(' ."') if 2 <= len(raw) <= 100 else None
    if field == 'code':
        code = raw.replace(' ', '').upper()
        return code if re.fullmatch(r'[A-Z0-9][A-Z0-9_.-]{1,19}', code) else None
    if field == 'groups':
        from app.assistant import find_programme, find_year, programmes
        pending = form.get('_programme')
        if pending and not find_programme(text, view['records']):
            # "Year 2" / "all years" answers "Which year of <programme>?"
            year = find_year(text) or (int(text) if re.fullmatch(r'\d', text) else None)
            if year or H(text, ('all', 'every', 'كل')):
                text = f"{normalise(pending)} year {year}" if year else f"all of {normalise(pending)}"
        found = groups_in(text, view)
        if found:
            form.pop('_programme', None)
            return found
        progs = find_programme(text, view['records'])
        if not progs:
            # One word shared by several programmes ("Informatics"): offer them.
            words = [w for w in re.findall(r'[a-z\u0600-\u06FF]{5,}', text)]
            progs = [p for p in programmes(view['records']) if any(mentions(normalise(p), w) for w in words)]
        if progs:
            return {'programmes': progs}  # a programme without a year, or a name that fits more than one: ask
        return None
    if field == 'kinds':
        kinds = [k for k, w in KINDS.items() if H(text, w)]
        if H(text, ('all three', 'all of them', 'everything', 'الثلاثة', 'كله')):
            kinds = ['lecture', 'tutorial', 'lab']
        return kinds or None
    if field in ('lecture', 'tutorial', 'lab'):
        if any(re.fullmatch(rf'{w}\.?', text) for w in NONE):
            return []  # decide later in Course setup
        ids, wrong = people_in(text, view, field)
        if wrong and not ids:
            return {'wrong': wrong}
        return ids or None
    return None


def step(slots, view, say):
    """The next question, or the whole plan to confirm."""
    form = slots.get('form') or {}
    if 'programmes' in (form.get('_last') or {}):
        progs = form.pop('_last')['programmes']
        groups = [r for r in view['records'] if r['kind'] == 'groups']
        if len(progs) > 1:
            return {'text': [say('Which programme do you mean?', 'تقصد أي برنامج؟')], 'asking': True, 'field': 'groups', 'form': form,
                    'choices': [{'label': p, 'text': p} for p in progs]}
        years = sorted({g['data'].get('year') for g in groups if g['data'].get('major') == progs[0] and g['data'].get('year')})
        form['_programme'] = progs[0]
        return {'text': [say(f'Which year of {progs[0]}?', f'أي سنة في {progs[0]}؟')], 'asking': True, 'field': 'groups', 'form': form,
                'choices': [{'label': say(f'Year {y}', f'سنة {y}'), 'text': f'{progs[0]} year {y}'} for y in years]
                           + ([{'label': say('All years', 'كل السنين'), 'text': f'all of {progs[0]}'}] if len(years) > 1 else [])}
    if 'wrong' in (form.get('_last') or {}):
        names = ', '.join(form['_last']['wrong'])
        form.pop('_last')
        need = {'lecture': say('doctors teach lectures', 'الدكاترة يدرسون المحاضرات'), 'tutorial': say('TAs teach tutorials', 'المعيدون يدرسون السكاشن'),
                'lab': say('TAs teach labs', 'المعيدون يدرسون المعامل')}[slots.get('field')]
        lead = [say(f'{names} cannot teach that ({need}).', f'{names} لا يمكنه تدريس ذلك ({need}).')]
    else:
        lead = [say("Sorry, I couldn't read that.", 'عذراً، لم أفهم الإجابة.')] if slots.get('unreadable') else []
    kinds = form.get('kinds') or []
    missing = [f for f in FIELDS if f not in form and (f in ('name', 'code', 'groups', 'kinds') or f in kinds)]
    if missing:
        field = missing[0]
        names = {r['id']: r['data'].get('code') for r in view['records'] if r['kind'] == 'groups'}
        if field == 'name':
            q, choices = say("What is the course called?", 'ما اسم المقرر؟'), []
        elif field == 'code':
            taken = {c['code'].upper() for c in view.get('catalog', [])}
            if form['name'].upper() in taken:
                pass
            q, choices = say(f"What is the code of {form['name']} (for example SEC301)?", f"ما كود {form['name']} (مثلاً SEC301)؟"), []
        elif field == 'groups':
            memory = (view.get('memory') or {})
            recent = [g for g in memory.get('groups', []) if g in names][:3] if memory.get('subject') == 'groups' else []
            q = say(f"Which student groups take {form['name']}? Type group codes, or a programme and year (for example \"IT Security year 3\").",
                    f"أي مجموعات تدرس {form['name']}؟ اكتب أكواد المجموعات أو البرنامج والسنة (مثلاً \"IT Security سنة 3\").")
            from app.assistant import programmes
            choices = [{'label': names[g], 'text': names[g]} for g in recent] + [{'label': p, 'text': p} for p in programmes(view['records'])][:10]
        elif field == 'kinds':
            q = say(f"What teaching does {form['name']} have each week?", f"ما نوع التدريس الأسبوعي في {form['name']}؟")
            choices = [{'label': say('Lecture + tutorial', 'محاضرة + سكشن'), 'text': 'lecture and tutorial'}, {'label': say('Lecture + lab', 'محاضرة + معمل'), 'text': 'lecture and lab'},
                       {'label': say('Lecture, tutorial and lab', 'محاضرة وسكشن ومعمل'), 'text': 'lecture, tutorial and lab'}, {'label': say('Lecture only', 'محاضرة فقط'), 'text': 'lecture'}]
        else:
            who = {'lecture': say('the lectures (doctors)', 'المحاضرات (دكاترة)'), 'tutorial': say('the tutorials (TAs)', 'السكاشن (معيدون)'), 'lab': say('the labs (TAs)', 'المعامل (معيدون)')}[field]
            q = say(f"Who can teach {who}? One or more names; or \"later\" to choose in Course setup.", f"من يدرّس {who}؟ اسم أو أكثر؛ أو \"بعدين\" للاختيار من إعداد المقررات.")
            choices = [{'label': n, 'text': n} for n in suggestions(view, form['groups'], field)] + [{'label': say('Decide later', 'لاحقاً'), 'text': 'later'}]
        return {'text': lead + [q], 'choices': choices, 'asking': True, 'field': field, 'form': form}
    return plan(form, view, say)


ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']


def lecture_sections(groups, view):
    """Split a lecture into sections that each fit the largest lecture hall, keeping a programme and year together.

    Groups are taken in programme, year and group-number order, so each section is a run of neighbouring groups,
    as the existing L-I, L-II, L-III sections are."""
    records = {r['id']: r['data'] for r in view['records']}
    halls = [r['data'].get('capacity') or 0 for r in view['records'] if r['kind'] == 'rooms'
             and set(r['data'].get('room_types') or [r['data'].get('room_type')]) & {'lecture', 'flexible'}]
    cap = max(halls, default=0)
    number = lambda g: int(m.group(1)) if (m := re.search(r'G(\d+)$', records[g].get('code', ''))) else 0
    ordered = sorted(groups, key=lambda g: (records[g].get('major') or '', records[g].get('year') or 0, number(g)))
    if not cap:
        return [ordered]
    sections, current, seats = [], [], 0
    for g in ordered:
        size = records[g].get('size') or 0
        if current and seats + size > cap:
            sections.append(current); current, seats = [], 0
        current.append(g); seats += size
    if current:
        sections.append(current)
    if len(sections) > 1:
        # Even them out: the same number of sections, groups shared as evenly as the order allows.
        per = -(-len(ordered) // len(sections))
        even = [ordered[i:i + per] for i in range(0, len(ordered), per)]
        if all(sum(records[g].get('size') or 0 for g in sec) <= cap for sec in even):
            sections = even
    return sections


def plan(form, view, say):
    """The catalogue course and its sessions, as Course setup would save them."""
    if any(c['code'].upper() == form['code'].upper() for c in view.get('catalog', [])):
        form.pop('code')
        return {'text': [say('A course with that code already exists. Which code should the new course have?', 'يوجد مقرر بهذا الكود. ما كود المقرر الجديد؟')],
                'asking': True, 'field': 'code', 'form': form}
    groups = form['groups']
    kinds = form['kinds']
    eligibility = {k: list(form.get(k) or []) for k in ('lecture', 'tutorial', 'lab')}
    records = {r['id']: r['data'] for r in view['records']}
    taken = {(r['data'].get('code') or '').upper() for r in view['records'] if r['kind'] == 'courses'}
    activities = []

    def code_for(base):
        code, n = base, 2
        while code.upper() in taken:
            code, n = f'{base}-{n}', n + 1
        taken.add(code.upper())
        return code[:20]
    teachers_ok = True
    for kind in kinds:
        if not eligibility[kind]:
            teachers_ok = False
            continue
        if kind == 'lecture':
            sections = lecture_sections(groups, view)
            for n, section in enumerate(sections):
                code = f"{form['code']}-L" + (f"-{ROMAN[n]}" if len(sections) > 1 else '')
                activities.append({'code': code_for(code), 'name': form['name'], 'activity_type': 'lecture', 'sessions': 1, 'duration': 90,
                                   'eligible_instructors': eligibility['lecture'], 'group_ids': section, 'required_equipment': []})
        else:
            for g in groups:
                suffix = re.search(r'G\d+$', records[g].get('code', '')) or None
                tag = suffix.group() if suffix else records[g].get('code', 'G')
                activities.append({'code': code_for(f"{form['code']}-{'LAB-' if kind == 'lab' else ''}{tag}"), 'name': form['name'], 'activity_type': kind,
                                   'sessions': 1, 'duration': 90, 'eligible_instructors': eligibility[kind], 'group_ids': [g], 'required_equipment': []})
    names = {i: records[i].get('name') for i in records}
    if len(groups) > 6:
        cohorts = sorted({(records[g].get('major'), records[g].get('year')) for g in groups}, key=lambda c: (c[0] or '', c[1] or 0))
        by = {}
        for major, year in cohorts:
            by.setdefault(major, []).append(str(year))
        who = say(f"{len(groups)} groups (" + '; '.join(f"{m} year {' and '.join(y)}" for m, y in by.items()) + ')',
                  f"{len(groups)} مجموعة (" + '؛ '.join(f"{m} سنة {' و'.join(y)}" for m, y in by.items()) + ')')
    else:
        who = ', '.join(records[g].get('code') for g in groups)
    lines = [say(f"Create {form['name']} ({form['code']}) for {who}:", f"إنشاء {form['name']} ({form['code']}) لـ {who}:")]
    for kind in kinds:
        people = ', '.join(names[t] for t in eligibility[kind]) or say('chosen later in Course setup', 'يُختار لاحقاً من إعداد المقررات')
        count = len(lecture_sections(groups, view)) if kind == 'lecture' else len(groups)
        label = {'lecture': say('lecture', 'محاضرة'), 'tutorial': say('tutorial', 'سكشن'), 'lab': say('lab', 'معمل')}[kind]
        note = say(f" (sections of up to {max(len(x) for x in lecture_sections(groups, view))} groups, so each fits a lecture hall)", ' (شعب تناسب القاعات)') if kind == 'lecture' and count > 1 else ''
        lines.append(say(f"• {count} {label}{'s' if count > 1 else ''}, 90 min once a week{note} · {people}", f"• {count} {label}، 90 دقيقة مرة أسبوعياً{note} · {people}"))
    if not teachers_ok:
        lines.append(say('Teaching without a named instructor is saved in the catalogue only; its sessions are added once you choose instructors in Course setup.',
                         'التدريس بدون محاضر يُحفظ في الكتالوج فقط؛ تُضاف حصصه بعد اختيار المحاضرين من إعداد المقررات.'))
    lines.append(say('Durations and weekly sessions can be changed later in Course setup.', 'يمكن تغيير المدد وعدد الحصص لاحقاً من إعداد المقررات.'))
    catalog = {'name': form['name'], 'code': form['code'], 'eligibility': eligibility, 'group_ids': groups, 'quiz_count': 3, 'second_chance': True}
    return {'text': lines, 'action': {'type': 'create_course', 'catalog': catalog, 'activities': activities, 'label': say('Create course', 'إنشاء المقرر')}}


def join_course(course, groups, view):
    """What Course setup would save to put these groups into a course: (catalogue body, session updates, new sessions).

    Each group joins one lecture section (the one its programme and year already use, the least full if
    several) and gets its own tutorial and lab copied from the course's existing ones."""
    records = {r['id']: r for r in view['records']}
    activities = [r for r in view['records'] if r['kind'] == 'courses' and r['data'].get('course_id') == course['id']]
    catalog = {k: course[k] for k in ('name', 'code', 'group_ids', 'quiz_count', 'second_chance')}
    catalog['eligibility'] = {k: list(v) for k, v in course['eligibility'].items()}
    if course.get('expected_students'):
        catalog['expected_students'] = course['expected_students']
    catalog['group_ids'] = list(dict.fromkeys(course['group_ids'] + groups))
    taken = {(r['data'].get('code') or '').upper() for r in view['records'] if r['kind'] == 'courses'}
    size = lambda a: sum(records.get(g, {}).get('data', {}).get('size') or 0 for g in a['data']['group_ids'])
    lectures = [a for a in activities if a['data']['activity_type'] == 'lecture']
    joined = {}
    for g in groups:
        cohort = (records[g]['data'].get('major'), records[g]['data'].get('year'))
        same = [a for a in lectures if any((records.get(x, {}).get('data', {}).get('major'), records.get(x, {}).get('data', {}).get('year')) == cohort for x in a['data']['group_ids'])]
        pick = min(same or lectures, key=size, default=None)
        if pick:
            joined.setdefault(pick['id'], []).append(g)
    updates = []
    for a in lectures:
        if a['id'] in joined:
            body = {k: v for k, v in a['data'].items() if k not in ('id', 'kind')}
            body['group_ids'] = list(dict.fromkeys(body['group_ids'] + joined[a['id']]))
            updates.append({'id': a['id'], 'body': body})
    creates = []
    for kind in ('tutorial', 'lab'):
        pattern = next((a['data'] for a in activities if a['data']['activity_type'] == kind), None)
        if not pattern:
            continue
        for g in groups:
            tag = (re.search(r'G\d+$', records[g]['data'].get('code', '')) or re.search(r'.+', records[g]['data'].get('code', 'G'))).group()
            code, n = f"{course['code']}-{'LAB-' if kind == 'lab' else ''}{tag}", 2
            while code.upper() in taken:
                code, n = f"{course['code']}-{'LAB-' if kind == 'lab' else ''}{tag}-{n}", n + 1
            taken.add(code.upper())
            creates.append({**{k: pattern[k] for k in ('name', 'activity_type', 'sessions', 'duration', 'eligible_instructors', 'required_equipment') if k in pattern},
                            'course_id': course['id'], 'code': code[:20], 'group_ids': [g]})
    return catalog, updates, creates


def sibling_courses(group_id, view):
    """Catalogue courses the other groups of this group's programme and year take."""
    records = {r['id']: r['data'] for r in view['records']}
    me = records.get(group_id, {})
    siblings = {i for i, d in records.items() if d.get('major') == me.get('major') and d.get('year') == me.get('year') and i != group_id and 'size' in d}
    return [c for c in view.get('catalog', []) if set(c['group_ids']) & siblings and group_id not in c['group_ids']]


def add_to_course(text, raw, view, say):
    """'Add IS3-G4 to Network Security' / 'add Dr. Sara to Network Security lectures'."""
    courses = catalog_named(text, view)
    if len(courses) != 1:
        return None
    course = courses[0]
    records = {r['id']: r for r in view['records']}
    activities = [r for r in view['records'] if r['kind'] == 'courses' and r['data'].get('course_id') == course['id']]
    rest = text.replace(normalise(course['name']), ' ').replace(normalise(course['code']), ' ')
    groups = [g for g in groups_in(rest, view) if g not in course['group_ids']]
    people, _ = find_records(rest, view['records'], 'instructors')
    catalog = {k: course[k] for k in ('name', 'code', 'eligibility', 'group_ids', 'quiz_count', 'second_chance')}
    catalog['eligibility'] = {k: list(v) for k, v in course['eligibility'].items()}
    if course.get('expected_students'):
        catalog['expected_students'] = course['expected_students']
    updates, creates, lines = [], [], []
    if groups:
        catalog, updates, creates = join_course(course, groups, view)
        lines.append(say(f"Add {', '.join(records[g]['data'].get('code') for g in groups)} to {course['name']} ({course['code']}): they join the shared lecture"
                         + (f", and get {len(creates)} tutorial/lab session(s) like the course's existing ones" if creates else '') + '.',
                         f"إضافة {', '.join(records[g]['data'].get('code') for g in groups)} إلى {course['name']} ({course['code']}): ينضمون للمحاضرة المشتركة"
                         + (f"، ويحصلون على {len(creates)} سكشن/معمل مثل الموجودة" if creates else '') + '.'))
    elif people:
        kind = next((k for k, w in KINDS.items() if H(rest, w)), None)
        person = people[0]
        position = person['data'].get('position')
        kind = kind or ('lecture' if position == 'doctor' else 'tutorial' if catalog['eligibility'].get('tutorial') or not catalog['eligibility'].get('lab') else 'lab')
        if position and POSITION[kind] != position:
            return {'text': [say(f"{person['data']['name']} is a {'doctor' if position == 'doctor' else 'TA'}; {'doctors teach lectures' if kind == 'lecture' else 'only TAs teach tutorials and labs'}.",
                                 f"{person['data']['name']} {'دكتور' if position == 'doctor' else 'معيد'}؛ {'الدكاترة يدرسون المحاضرات' if kind == 'lecture' else 'المعيدون فقط يدرسون السكاشن والمعامل'}.")]}
        if person['id'] in catalog['eligibility'][kind]:
            return {'text': [say(f"{person['data']['name']} can already teach {course['name']} {kind}s.", f"{person['data']['name']} يستطيع بالفعل تدريس {course['name']}.")]}
        catalog['eligibility'][kind] = catalog['eligibility'][kind] + [person['id']]
        for a in activities:
            if a['data']['activity_type'] == kind:
                body = {k: v for k, v in a['data'].items() if k not in ('id', 'kind')}
                body['eligible_instructors'] = list(dict.fromkeys(body['eligible_instructors'] + [person['id']]))
                updates.append({'id': a['id'], 'body': body})
        lines.append(say(f"Let {person['data']['name']} teach {course['name']} ({course['code']}) {kind}s ({len(updates)} session(s))?",
                         f"السماح لـ{person['data']['name']} بتدريس {course['name']} ({course['code']}) ({len(updates)} حصة)؟"))
    else:
        return {'text': [say(f"What should I add to {course['name']}? A group (\"add IS3-G4 to {course['name']}\") or an instructor (\"add Dr. X to {course['name']} lectures\").",
                             f"ماذا أضيف إلى {course['name']}؟ مجموعة أو محاضر.")]}
    return {'text': lines, 'action': {'type': 'update_course', 'course_id': course['id'], 'catalog': catalog, 'updates': updates, 'creates': creates,
                                      'label': say('Save', 'حفظ')}}
