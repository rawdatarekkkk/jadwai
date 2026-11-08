"""Repair suggestions for a teaching timetable that cannot satisfy every constraint.

Candidates are the things an administrator could reasonably change: each approved rule,
each fixed session (lock), each instructor's day off, and each daily policy limit. The
diagnosis relaxes all of them; if a valid timetable then exists, it puts candidates back a
chunk at a time while one still exists, leaving a minimal set that must give way. A final
solve with only that set relaxed shows exactly which sessions are affected (for a fixed
session: where it moves to), and the independent validator checks that timetable against
everything else. Hard data limits (rooms, eligible instructors, the "every TA teaches"
rule, the calendar itself) are never relaxed; if relaxing everything still fails, the
answer is that the data must change, with the input checks that say where.
"""
import copy
import time
from collections import defaultdict
from app import rule_semantics as rs

POLICY_FIELDS = {
    'student_daily_hours': ('Student daily hours limit', None),
    'instructor_daily_hours': ('Instructor daily hours limit', None),
    'max_consecutive_periods': ('Most consecutive periods', None),
    'max_idle_periods': ('Most free periods in a day', None),
    'spread_activity_days': ('Sessions of one course on different days', False),
}
POLICY_AR = {'student_daily_hours': 'حد ساعات الطلاب اليومي', 'instructor_daily_hours': 'حد ساعات المدرسين اليومي',
             'max_consecutive_periods': 'أقصى فترات متتالية', 'max_idle_periods': 'أقصى فترات فراغ في اليوم',
             'spread_activity_days': 'حصص المقرر في أيام مختلفة'}
AR_DAYS = {'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الإثنين', 'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء', 'Thursday': 'الخميس', 'Friday': 'الجمعة'}
RELAXED_RULE_TYPES = [t for t in rs.TYPES if t != 'preferred_period']  # preferences are already soft


def clock(m):
    return f'{m // 60:02d}:{m % 60:02d}'


def candidates(snapshot):
    """Everything the diagnosis may relax, as (key, kind, target)."""
    found = [(f"rule:{r['id']}", 'rule', r) for r in rs.approved(snapshot, *RELAXED_RULE_TYPES)]
    found += [(f"lock:{l.get('id') or i}", 'lock', l) for i, l in enumerate(snapshot.get('assignment_locks', [])) if l.get('status') == 'approved']
    found += [(f"day_off:{r['id']}", 'day_off', r) for r in snapshot['records'] if r['kind'] == 'instructors' and r.get('day_off')]
    policy = snapshot['calendar'].get('realism_policy') or {}
    found += [(f'policy:{k}', 'policy', k) for k in POLICY_FIELDS if policy.get(k) not in (None, False)]
    return found


def relax(snapshot, items):
    """A copy of the snapshot with the given candidates removed."""
    snap = copy.deepcopy(snapshot)
    keys = {key for key, _, _ in items}
    snap['rules'] = [r for r in snap['rules'] if f"rule:{r['id']}" not in keys]
    snap['assignment_locks'] = [l for i, l in enumerate(snap.get('assignment_locks', [])) if f"lock:{l.get('id') or i}" not in keys]
    for r in snap['records']:
        if f"day_off:{r['id']}" in keys:
            r['day_off'] = None
    policy = dict(snap['calendar'].get('realism_policy') or {})
    for key in keys:
        if key.startswith('policy:'):
            policy[key[7:]] = POLICY_FIELDS[key[7:]][1]
    snap['calendar'] = {**snap['calendar'], 'realism_policy': policy}
    return snap


def solve(snapshot, seconds, cancel=None):
    """('feasible', assignments) | ('infeasible', reason) | ('unknown', reason) for a quick feasibility search."""
    from app.provenance import CONFIG
    from app.solver import generate
    from app.validation import validate_schedule
    config = {**snapshot.get('provenance', {}).get('solver_config', CONFIG), 'objective_profile': 'preferences-first-v1', 'time_limit_seconds': seconds}
    snap = {**snapshot, 'provenance': {**snapshot.get('provenance', {}), 'solver_config': config}}
    result = generate(snap, cancel, time_limit=seconds)
    if result['status'] == 'completed':
        report = validate_schedule(snapshot, result['assignments'])
        return ('feasible', result['assignments']) if report['passed'] else ('infeasible', 'validation_failed')
    if result['status'] == 'unknown':
        return 'unknown', result.get('reason')
    return 'infeasible', result.get('reason')


LOCAL_ABOVE = 80  # sessions; larger timetables are diagnosed around the conflict first


def neighbourhood(snapshot, seeds, hops):
    """Activity ids of the seeds plus those sharing a group or an eligible instructor, `hops` times."""
    acts = {r['id']: r for r in snapshot['records'] if r['kind'] == 'courses'}
    chosen = {a for a in seeds if a in acts}
    for _ in range(hops):
        groups = {g for a in chosen for g in acts[a]['group_ids']}
        teachers = {t for a in chosen for t in acts[a]['eligible_instructors']}
        chosen |= {i for i, a in acts.items() if groups & set(a['group_ids']) or teachers & set(a['eligible_instructors'])}
    return chosen


def seeds_of(snapshot, hints=()):
    """Activities a failure points at: named ones, fixed sessions, and those a rule mentions."""
    acts = [r for r in snapshot['records'] if r['kind'] == 'courses']
    seeds = set(hints) | {l['activity_id'] for l in snapshot.get('assignment_locks', []) if l.get('status') == 'approved'}
    for rule in rs.approved(snapshot, *RELAXED_RULE_TYPES):
        seeds |= {a['id'] for a in acts if a['id'] == rule.get('activity_id') or a['id'] in (rs.param(rule, 'activity_ids') or [])
                  or rule.get('group_id') in a['group_ids'] or rule.get('instructor_id') in a['eligible_instructors']}
    return seeds


def part_of(snapshot, activity_ids):
    """The snapshot limited to some activities, as a part run (other activities are simply not scheduled)."""
    return {**snapshot, 'plan': {'scope': [], 'base_run_id': None, 'activity_ids': sorted(activity_ids), 'fixed': []}}


def diagnose(snapshot, budget=240, step=30, cancel=None, hints=()):
    """Find a minimal fix, around the conflict first on large timetables, then verify it on the whole."""
    sessions = sum(r['sessions'] for r in snapshot['records'] if r['kind'] == 'courses')
    if sessions <= LOCAL_ABOVE or snapshot.get('plan'):
        return search(snapshot, budget, step, cancel)
    started = time.monotonic()
    seeds = seeds_of(snapshot, hints)
    for hops in (1, 2):
        area = neighbourhood(snapshot, seeds, hops)
        if not area:
            break
        local = part_of(snapshot, area)
        if solve(local, 10, cancel)[0] == 'feasible':
            continue  # the conflict is not in this part; look wider
        found = search(local, min(120, budget / 2), 8, cancel)
        if found['status'] != 'fixable':
            return found
        # Prove the same fix on the whole timetable.
        keys = {s['key'] for s in found['suggestions']}
        chosen = [c for c in candidates(snapshot) if c[0] in keys]
        left = budget - (time.monotonic() - started)
        status, rows = solve(relax(snapshot, chosen), max(5, left), cancel) if left > 5 else ('unknown', None)
        if status == 'feasible':
            from app.validation import validate_schedule
            return {'status': 'fixable', 'verified': validate_schedule(relax(snapshot, chosen), rows)['passed'], 'solves': found['solves'] + 1,
                    'relaxable': len(candidates(snapshot)), 'checked_sessions': sum(r['sessions'] for r in local['records'] if r['kind'] == 'courses' and r['id'] in area),
                    'suggestions': [{**describe(snapshot, kind, target, rows), 'key': key} for key, kind, target in chosen], 'assignments': rows}
        return {**found, 'verified': False, 'note': 'Found in the affected part of the timetable; the whole timetable could not be checked in time.',
                'note_ar': 'وُجد في الجزء المتأثر من الجدول؛ لم يمكن فحص الجدول كله في الوقت المتاح.'}
    left = budget - (time.monotonic() - started)
    return search(snapshot, left, step, cancel)


def search(snapshot, budget=240, step=30, cancel=None):
    """Minimal set of candidates to relax, with verified effects, or why none exists."""
    started = time.monotonic()
    calls = [0]

    def feasible(items, seconds=step):
        calls[0] += 1
        left = budget - (time.monotonic() - started)
        if left < 2 or (cancel and cancel.is_set()):
            raise TimeoutError
        return solve(relax(snapshot, items), min(seconds, left), cancel)

    pool = candidates(snapshot)
    try:
        status, value = feasible(pool)
        if status != 'feasible':
            from app.preflight import inspect_inputs
            checked = inspect_inputs(relax(snapshot, pool))['blockers'][:10]
            findings, findings_ar = [b['message'] for b in checked], [b['message_ar'] for b in checked]
            return {'status': 'data_change_needed' if status == 'infeasible' else 'not_found', 'reason': value, 'relaxable': len(pool), 'solves': calls[0], 'findings': findings, 'findings_ar': findings_ar,
                    'message': 'Even with every rule, lock, day off and daily limit relaxed, no timetable fits: rooms, eligible instructors or sessions must change. See Check inputs.'
                    if status == 'infeasible' else 'The search did not finish in time, so no fix was proven.',
                    'message_ar': 'حتى مع تخفيف كل القيود والحصص المثبتة وأيام الإجازة والحدود اليومية لا يوجد جدول ممكن: يجب تغيير القاعات أو المدرسين المؤهلين أو الحصص. راجع فحص المدخلات.'
                    if status == 'infeasible' else 'لم ينتهِ البحث في الوقت المتاح، لذلك لم يُثبت أي حل.'}
        # Put candidates back a chunk at a time, keeping each chunk unless the timetable breaks.
        needed, kept_relaxed, best = [], list(pool), value
        stack = [pool]
        while stack:
            chunk = stack.pop()
            trial = [c for c in kept_relaxed if c not in chunk]
            status, value = feasible(trial)
            if status == 'feasible':
                kept_relaxed, best = trial, value
            elif len(chunk) == 1:
                # An inconclusive search is not proof: look longer before calling it necessary.
                if status == 'unknown':
                    status, value = feasible(trial, step * 4)
                    if status == 'feasible':
                        kept_relaxed, best = trial, value
                        continue
                needed.append(chunk[0])
            else:
                half = len(chunk) // 2
                stack += [chunk[half:], chunk[:half]]
    except TimeoutError:
        return {'status': 'not_found', 'solves': calls[0], 'message': 'The diagnosis ran out of time before finding a proven fix.',
                'message_ar': 'انتهى وقت التشخيص قبل العثور على حل مثبت.'}
    from app.validation import validate_schedule
    relaxed_snapshot = relax(snapshot, kept_relaxed)
    verified = validate_schedule(relaxed_snapshot, best)['passed']
    return {'status': 'fixable', 'verified': verified, 'solves': calls[0], 'relaxable': len(pool),
            'suggestions': [{**describe(snapshot, kind, target, best), 'key': key} for key, kind, target in kept_relaxed],
            'assignments': best}


def describe(snapshot, kind, target, rows):
    """One suggestion in plain words, with the sessions it affects in the repaired timetable."""
    records = {r['id']: r for r in snapshot['records']}
    name = lambda i: records.get(i, {}).get('name') or i
    def session(a):
        act = records.get(a['activity_id'], {})
        from app.timetable_pdf import compact_groups
        groups = compact_groups([records.get(g, {}).get('code') or g for g in act.get('group_ids', [])])
        return f"{act.get('name') or a['activity_id']} ({groups}) {a['day']} {clock(a['start_minute'])} in {name(a['room_id'])} with {name(a['instructor_id'])}"
    def session_ar(a):
        act = records.get(a['activity_id'], {})
        from app.timetable_pdf import compact_groups
        groups = compact_groups([records.get(g, {}).get('code') or g for g in act.get('group_ids', [])])
        return f"{act.get('name') or a['activity_id']} ({groups}) {AR_DAYS.get(a['day'], a['day'])} {clock(a['start_minute'])} في {name(a['room_id'])} مع {name(a['instructor_id'])}"
    day_ar = lambda d: AR_DAYS.get(d, d) if d else 'كل يوم'
    groups_of = lambda a: set(records.get(a['activity_id'], {}).get('group_ids', []))
    if kind == 'lock':
        moved = next((a for a in rows if a['activity_id'] == target['activity_id'] and a['occurrence'] == target['occurrence']), None)
        was = ' '.join(x for x in [target.get('day') or '', clock(target['start_minute']) if target.get('start_minute') is not None else '',
                                   f"in {name(target['room_id'])}" if target.get('room_id') else '', f"with {name(target['instructor_id'])}" if target.get('instructor_id') else ''] if x)
        was_ar = ' '.join(x for x in [day_ar(target.get('day')) if target.get('day') else '', clock(target['start_minute']) if target.get('start_minute') is not None else '',
                                      f"في {name(target['room_id'])}" if target.get('room_id') else '', f"مع {name(target['instructor_id'])}" if target.get('instructor_id') else ''] if x)
        return {'kind': 'move_session', 'target': target.get('id'), 'title': f"Move {name(target['activity_id'])} (session {target['occurrence'] + 1})",
                'message': f"It is fixed at {was}, which cannot work with the other constraints. Move it to {moved['day']} {clock(moved['start_minute'])} in {name(moved['room_id'])} with {name(moved['instructor_id'])}." if moved else 'Release this fixed session.',
                'sessions': [session(moved)] if moved else [],
                'title_ar': f"انقل {name(target['activity_id'])} (الحصة {target['occurrence'] + 1})",
                'message_ar': f"هي مثبتة في {was_ar}، وهذا لا يتوافق مع القيود الأخرى. انقلها إلى {day_ar(moved['day'])} {clock(moved['start_minute'])} في {name(moved['room_id'])} مع {name(moved['instructor_id'])}." if moved else 'ألغِ تثبيت هذه الحصة.',
                'sessions_ar': [session_ar(moved)] if moved else []}
    if kind == 'day_off':
        hit = [a for a in rows if a['instructor_id'] == target['id'] and a['day'] == target['day_off']]
        return {'kind': 'day_off', 'target': target['id'], 'title': f"{name(target['id'])} teaches on their day off ({target['day_off']})",
                'message': f"Ask {name(target['id'])} to teach {len(hit)} session(s) on {target['day_off']}, move their day off, or make another instructor eligible.",
                'sessions': [session(a) for a in hit],
                'title_ar': f"{name(target['id'])} يدرّس في يوم إجازته ({day_ar(target['day_off'])})",
                'message_ar': f"اطلب من {name(target['id'])} تدريس {len(hit)} حصة يوم {day_ar(target['day_off'])}، أو غيّر يوم إجازته، أو اجعل مدرسًا آخر مؤهلًا.",
                'sessions_ar': [session_ar(a) for a in hit]}
    if kind == 'policy':
        label, _ = POLICY_FIELDS[target]
        limit = (snapshot['calendar'].get('realism_policy') or {}).get(target)
        need = policy_need(snapshot, target, rows)
        return {'kind': 'policy', 'target': target, 'title': f"Relax: {label} ({limit if limit is not True else 'on'})",
                'message': f"{label}: the timetable needs {need['value']} for {need['who']}." if need else f"{label} cannot be met; relax it.",
                'sessions': [], 'sessions_ar': [],
                'title_ar': f"خفّف: {POLICY_AR[target]} ({limit if limit is not True else 'مفعّل'})",
                'message_ar': f"{POLICY_AR[target]}: يحتاج الجدول {need['value_ar']} لـ {need['who_ar']}." if need else f"لا يمكن تحقيق {POLICY_AR[target]}؛ خفّفه."}
    rule = target
    title = rule.get('title') or rule['type'].replace('_', ' ')
    t = rule['type']
    if t in ('unavailable', 'room_unavailable', 'group_unavailable'):
        field = {'unavailable': 'instructor_id', 'room_unavailable': 'room_id', 'group_unavailable': 'group_id'}[t]
        hit = [a for a in rows if rs.overlaps(rule, a['day'], a['start_minute'], a['end_minute'])
               and (a['instructor_id'] == rule['instructor_id'] if t == 'unavailable' else a['room_id'] == rule['room_id'] if t == 'room_unavailable' else rule['group_id'] in groups_of(a))]
        when = f"{rule.get('day') or 'every day'} {clock(rs.bounds(rule)[0])}–{clock(rs.bounds(rule)[1])}"
        message = f"{name(rule[field])} is unavailable {when}, but {len(hit)} session(s) need that time. Shorten or lift this rule, or add another eligible instructor or room."
        when_ar = f"{day_ar(rule.get('day'))} {clock(rs.bounds(rule)[0])}–{clock(rs.bounds(rule)[1])}"
        message_ar = f"{name(rule[field])} غير متاح {when_ar}، لكن {len(hit)} حصة تحتاج هذا الوقت. قصّر هذا القيد أو ألغه، أو أضف مدرسًا أو قاعة مؤهلة أخرى."
    elif t in ('group_allowed', 'activity_allowed'):
        field = 'group_id' if t == 'group_allowed' else 'activity_id'
        windows = [r for r in rs.approved(snapshot, t) if r.get(field) == rule[field]]
        hit = [a for a in rows if (rule[field] in groups_of(a) if t == 'group_allowed' else a['activity_id'] == rule[field]) and not rs.within_windows(windows, a['day'], a['start_minute'], a['end_minute'])]
        message = f"{name(rule[field])} is limited to certain times, but {len(hit)} session(s) need other times. Widen the allowed times."
        message_ar = f"{name(rule[field])} مقيد بأوقات معينة، لكن {len(hit)} حصة تحتاج أوقاتًا أخرى. وسّع الأوقات المسموح بها."
    elif t == 'activity_room':
        hit = [a for a in rows if a['activity_id'] == rule['activity_id'] and a['room_id'] not in rs.param(rule, 'room_ids')]
        message = f"{name(rule['activity_id'])} is limited to specific rooms that are not free; allow another room."
        message_ar = f"{name(rule['activity_id'])} مقيد بقاعات محددة غير متاحة؛ اسمح بقاعة أخرى."
    elif t == 'activities_not_same_day':
        days = defaultdict(set)
        for a in rows:
            if a['activity_id'] in rs.param(rule, 'activity_ids'):
                days[a['day']].add(a['activity_id'])
        hit = [a for a in rows if a['activity_id'] in rs.param(rule, 'activity_ids') and len(days[a['day']]) > 1]
        message = 'These courses cannot all be on separate days; allow two of them on the same day.'
        message_ar = 'لا يمكن وضع كل هذه المقررات في أيام مختلفة؛ اسمح باثنين منها في نفس اليوم.'
    else:  # daily hours or teaching-day limits
        who = rule.get('instructor_id') or rule.get('group_id')
        mine = [a for a in rows if (a['instructor_id'] == who if rule.get('instructor_id') else who in groups_of(a))]
        per_day = defaultdict(int)
        for a in mine:
            per_day[a['day']] += records[a['activity_id']]['duration']
        if t == 'instructor_max_days':
            message = f"{name(who)} needs {len(per_day)} teaching days; the limit is {rs.param(rule, 'days')}. Raise it to {len(per_day)}."
            message_ar = f"يحتاج {name(who)} إلى {len(per_day)} أيام تدريس؛ والحد {rs.param(rule, 'days')}. ارفعه إلى {len(per_day)}."
        else:
            most = max(per_day.values(), default=0) / 60
            message = f"{name(who)} needs {most:g} hours on the busiest day; the limit is {rs.param(rule, 'hours')} h. Raise it to {most:g} h."
            message_ar = f"يحتاج {name(who)} إلى {most:g} ساعة في أكثر الأيام ازدحامًا؛ والحد {rs.param(rule, 'hours')} ساعة. ارفعه إلى {most:g} ساعة."
        hit = []
    return {'kind': 'rule', 'target': rule['id'], 'title': f'Relax rule: {title}', 'message': message, 'sessions': [session(a) for a in hit],
            'title_ar': f'خفّف القيد: {title}', 'message_ar': message_ar, 'sessions_ar': [session_ar(a) for a in hit]}


def policy_need(snapshot, field, rows):
    """What the repaired timetable actually needs for a relaxed daily policy."""
    from app.realism_validation import occupancy, gaps
    from app.calendar_slots import day_slots
    records = {r['id']: r for r in snapshot['records']}
    used = occupancy(snapshot, rows)
    slots = day_slots(snapshot['calendar'])
    def runs(s):
        best = cur = 0
        prev = None
        for i in sorted(s):
            cur = cur + 1 if prev is not None and i == prev + 1 else 1
            best, prev = max(best, cur), i
        return best
    measure = {'student_daily_hours': ('group', lambda s: sum(slots[i][1] - slots[i][0] for i in s) / 60, 'h', 'ساعة'),
               'instructor_daily_hours': ('instructor', lambda s: sum(slots[i][1] - slots[i][0] for i in s) / 60, 'h', 'ساعة'),
               'max_consecutive_periods': ('group', runs, 'periods in a row', 'فترات متتالية'),
               'max_idle_periods': ('group', gaps, 'free periods', 'فترات فراغ')}.get(field)
    if not measure:
        return None
    kind, f, unit, unit_ar = measure
    worst = max(((f(s), ident, day) for (k, ident, day), s in used.items() if k == kind), default=None)
    if not worst:
        return None
    who = records.get(worst[1], {}).get('name', worst[1])
    return {'value': f'{worst[0]:g} {unit}', 'who': f"{who} on {worst[2]}",
            'value_ar': f'{worst[0]:g} {unit_ar}', 'who_ar': f"{who} يوم {AR_DAYS.get(worst[2], worst[2])}"}
