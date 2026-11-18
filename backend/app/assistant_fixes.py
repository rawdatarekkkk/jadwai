"""JAI finds what would stop a timetable and proposes fixes.

The input checks (preflight) name the blocked sessions; this turns them into plain reasons and, where
there is a safe change to make, into the same website requests Course setup and Academic data send:

* a lecture larger than every hall is split into sections that each fit (as L-I, L-II…);
* a group larger than every room of the kind its sessions need is set to that room's size
  (said plainly: if the group really is larger, splitting the group is the other way out).

Problems without a safe automatic change (no instructor can teach it, a special room is missing,
rules leave no time) are explained with where to fix them. Nothing changes until the admin confirms.
"""
from collections import defaultdict

ROOM_WORDS = {'lecture': ('lecture hall', 'قاعة محاضرات'), 'lab': ('lab', 'معمل'), 'tutorial': ('tutorial room', 'قاعة سكشن')}


def room_capacity(view, kind):
    """The largest room a session of this kind may use."""
    rooms = [r['data'] for r in view['records'] if r['kind'] == 'rooms' and not r['data'].get('reserved_majors') and not r['data'].get('reserved_course_ids')]
    fits = [r.get('capacity') or 0 for r in rooms if kind in (r.get('room_types') or [r.get('room_type')]) or 'flexible' in (r.get('room_types') or [])]
    return max(fits, default=0)


def body_of(record):
    return {k: v for k, v in record['data'].items() if k not in ('id', 'kind')}


def diagnose(view, checks, groups=None, say=lambda en, ar: en):
    """{'lines', 'steps', 'open', 'count'} for the blockers touching these groups (all when None)."""
    from app.assistant_courses import ROMAN, lecture_sections
    records = {r['id']: r for r in view['records']}
    blockers = checks.get('blockers', [])
    by_activity = defaultdict(set)
    other = []
    for b in blockers:
        a = records.get(b.get('activity_id'))
        if a and a['kind'] == 'courses':
            if groups is None or set(a['data'].get('group_ids', [])) & set(groups):
                by_activity[a['id']].add(b['code'])
        elif groups is None:
            other.append(b)
    lines, steps, opens = [], [], set()
    resize = {}  # group -> (new size, [activity codes])
    split_choices = []
    for aid, codes in by_activity.items():
        a = records[aid]
        d = a['data']
        kind = d['activity_type']
        size = sum(records.get(g, {}).get('data', {}).get('size') or 0 for g in d['group_ids'])
        cap = room_capacity(view, kind)
        where = ROOM_WORDS.get(kind, ('room', 'قاعة'))
        if 'no_suitable_room' in codes and cap and size > cap:
            if kind == 'lecture' and len(d['group_ids']) > 1:
                sections = lecture_sections(d['group_ids'], view)
                lines.append(say(f"{d['code']} puts {size} students in one lecture; the largest {where[0]} seats {cap}. I'll split it into {len(sections)} sections of up to {max(len(s) for s in sections)} groups.",
                                 f"{d['code']} تضع {size} طالباً في محاضرة واحدة؛ أكبر {where[1]} تسع {cap}. سأقسمها إلى {len(sections)} شعب."))
                taken = {(r['data'].get('code') or '').upper() for r in view['records'] if r['kind'] == 'courses'}
                for n, section in enumerate(sections):
                    code = f"{d['code']}-{ROMAN[n]}"
                    while code.upper() in taken and n:
                        code += 'X'
                    if n == 0:
                        steps.append({'method': 'PUT', 'path': f"/records/courses/{aid}", 'body': {**body_of(a), 'code': code, 'group_ids': section}})
                    else:
                        steps.append({'method': 'POST', 'path': '/records/courses', 'body': {**body_of(a), 'code': code, 'group_ids': section}})
                    taken.add(code.upper())
                continue
            if len(d['group_ids']) == 1:
                g = d['group_ids'][0]
                new, acts = resize.get(g, (cap, []))
                resize[g] = (min(new, cap), acts + [d['code']])
                continue
        if 'no_suitable_room' in codes:
            lines.append(say(f"{d['code']}: no {where[0]} fits it (its size, a special-room feature it needs, or rooms reserved for other programmes). Check it in Course setup.",
                             f"{d['code']}: لا توجد {where[1]} تناسبها (الحجم أو تجهيزات خاصة أو قاعات محجوزة). راجعها في إعداد المقررات."))
            opens.add('courses')
        elif 'no_available_placement' in codes:
            teachers = [records.get(t, {}).get('data', {}).get('name') for t in d.get('eligible_instructors', [])]
            lines.append(say(f"{d['code']}: no time works for it. Its instructors ({', '.join(t for t in teachers if t) or 'none'}) may be unavailable, or rules close all its slots. Add another instructor or relax a rule.",
                             f"{d['code']}: لا يوجد وقت مناسب. قد يكون محاضروها ({', '.join(t for t in teachers if t) or 'لا أحد'}) غير متاحين أو القيود تغلق كل الفترات. أضف محاضراً أو خفف قيداً."))
            opens.add('courses')
        else:
            lines.append(say(f"{d['code']}: " + ', '.join(c.replace('_', ' ') for c in sorted(codes)) + '.', f"{d['code']}: " + '، '.join(sorted(codes)) + '.'))
    for g, (new, acts) in resize.items():
        group = records[g]
        split_choices.append({'label': say(f"Split {group['data']['code']} into two groups", f"قسّم {group['data']['code']} لمجموعتين"), 'text': f"split {group['data']['code']} into two groups"})
        lines.append(say(f"{group['data']['code']} has {group['data'].get('size')} students, but the largest room its {', '.join(acts[:3])}{'…' if len(acts) > 3 else ''} can use seats {new}. "
                         f"I'll set {group['data']['code']} to {new} students. If it really has {group['data'].get('size')}, split it into two groups instead.",
                         f"{group['data']['code']} بها {group['data'].get('size')} طالباً، لكن أكبر قاعة متاحة لحصصها تسع {new}. سأجعل عددها {new}. إن كانت فعلاً {group['data'].get('size')}، قسّمها لمجموعتين بدلاً من ذلك."))
        steps.insert(0, {'method': 'PUT', 'path': f"/records/groups/{g}", 'body': {**body_of(group), 'size': new}})
    for b in other[:5]:
        lines.append(b.get('message') or b['code'].replace('_', ' '))
    count = len(by_activity) + len(other)
    return {'lines': lines, 'steps': steps, 'open': sorted(opens), 'count': count, 'choices': split_choices}


def reply(diagnosis, say, then=None, intro=None):
    """The answer: what is wrong, what JAI will change, and one button to do it (and then generate)."""
    if not diagnosis['count']:
        return None
    text = [intro or say(f"{diagnosis['count']} session(s) can't be scheduled as things are:", f"{diagnosis['count']} حصة لا يمكن جدولتها بالوضع الحالي:")]
    text += ['• ' + line for line in diagnosis['lines'][:12]]
    out = {'text': text, 'choices': diagnosis.get('choices') or []}
    if diagnosis['steps']:
        label = say('Fix and generate', 'إصلاح ثم إنشاء') if then else say('Fix these', 'إصلاح')
        out['action'] = {'type': 'apply_changes', 'steps': diagnosis['steps'], 'then': then, 'label': label}
        if diagnosis['open']:
            text.append(say('Some problems need a decision in Course setup; I can fix the rest now.', 'بعض المشاكل تحتاج قراراً في إعداد المقررات؛ أستطيع إصلاح الباقي الآن.'))
    elif diagnosis['open']:
        out['action'] = {'type': 'open', 'page': diagnosis['open'][0], 'label': say('Open Course setup', 'فتح إعداد المقررات')}
    return out


def split_group(group_id, view, say=lambda en, ar: en):
    """Split a group into two of about half the size: the second takes every course the first takes
    (the same lecture section, its own tutorials and labs). Steps for the chat window; '$new' is the
    new group's id once the step that creates it has run."""
    import re
    from app.assistant_courses import join_course
    records = {r['id']: r for r in view['records']}
    group = records.get(group_id)
    if not group or group['kind'] != 'groups':
        return None
    d = group['data']
    size = d.get('size') or 0
    if size < 2:
        return {'text': [say(f"{d['code']} has too few students to split.", f"{d['code']} بها عدد قليل جداً للتقسيم.")]}
    first, second = (size + 1) // 2, size // 2
    m = re.match(r'^(.*?G)(\d+)$', d.get('code', ''))
    taken = {(r['data'].get('code') or '').upper() for r in view['records'] if r['kind'] == 'groups'}
    if m:
        prefix, n = m.group(1), int(m.group(2))
        siblings = [int(x.group(1)) for r in view['records'] if r['kind'] == 'groups' and (x := re.match(re.escape(prefix) + r'(\d+)$', r['data'].get('code', '')))]
        number = max(siblings + [n]) + 1
        code = f'{prefix}{number}'
        name = re.sub(r'G\d+$', f'G{number}', d.get('name', '')) if re.search(r'G\d+$', d.get('name', '')) else f"{d.get('name')} (2)"
    else:
        code, name = f"{d['code']}-2", f"{d.get('name')} (2)"
    while code.upper() in taken:
        code += 'B'
    new = {'name': name, 'code': code, 'size': second, 'year': d.get('year'), 'major': d.get('major')}
    steps = [{'method': 'PUT', 'path': f'/records/groups/{group_id}', 'body': {**body_of(group), 'size': first}},
             {'method': 'POST', 'path': '/records/groups', 'body': new, 'save_as': 'new'}]
    # The new group joins every course the old one takes, as if it had always been there.
    shadow = {**view, 'records': [*view['records'], {'id': '$new', 'kind': 'groups', 'data': new}]}
    courses = [c for c in view.get('catalog', []) if group_id in c['group_ids']]
    sessions = 0
    for course in courses:
        catalog, updates, creates = join_course(course, ['$new'], shadow)
        # Join the same lecture section as the old group, not just the least full one.
        lectures = [r for r in view['records'] if r['kind'] == 'courses' and r['data'].get('course_id') == course['id'] and r['data']['activity_type'] == 'lecture']
        mine = next((a for a in lectures if group_id in a['data']['group_ids']), None)
        if mine:
            updates = [u for u in updates if u['id'] not in {a['id'] for a in lectures}]
            updates.append({'id': mine['id'], 'body': {**body_of(mine), 'group_ids': mine['data']['group_ids'] + ['$new']}})
        steps.append({'method': 'PUT', 'path': f"/course-catalog/{course['id']}", 'body': catalog})
        steps += [{'method': 'PUT', 'path': f"/records/courses/{u['id']}", 'body': u['body']} for u in updates]
        steps += [{'method': 'POST', 'path': '/records/courses', 'body': c} for c in creates]
        sessions += len(creates)
    return {'text': [say(f"Split {d['code']} ({size} students) into {d['code']} ({first}) and a new {code} ({second})?",
                         f"تقسيم {d['code']} ({size} طالباً) إلى {d['code']} ({first}) و{code} جديدة ({second})؟"),
                     say(f"{code} joins all {len(courses)} of its courses: the same lecture sections, and {sessions} tutorial/lab sessions of its own.",
                         f"تنضم {code} إلى كل مقرراتها الـ{len(courses)}: نفس شعب المحاضرات، و{sessions} سكشن/معمل خاص بها."),
                     say('Student accounts stay with the original group; move students to the new one in Accounts if needed.',
                         'حسابات الطلاب تبقى مع المجموعة الأصلية؛ انقلها للجديدة من الحسابات إن لزم.')],
            'action': {'type': 'apply_changes', 'steps': steps, 'then': None, 'label': say('Split it', 'تقسيم')}}
