"""'A better timetable': JAI looks at a group's week, proposes changes, and on confirm applies them and regenerates.

Goals it understands: free days for students ("two free days", "a day off"), a later start ("no classes
before 10"), an earlier finish ("finish by 2pm"), and fewer gaps. Free days are chosen as the lightest
days of the group's current week (the same days for every group asked about, so a programme keeps one
shared day off), and only when the rest of the week can still hold its sessions. The changes become
approved rules (removable later: "remove the rule for BA5-G7"), then the groups are generated again inside
the published timetable, so everyone else keeps their week. Nothing changes until the admin confirms.
"""
import math
import re
from app.rule_parser import mentions, normalise

NUMBERS = {'one': 1, 'a': 1, 'an': 1, 'two': 2, 'three': 3, 'four': 4, 'واحد': 1, 'يوم': 1, 'اتنين': 2, 'يومين': 2, 'تلاتة': 3, 'ثلاثة': 3, 'تلات': 3}
FREE_DAY = r'(?:free|off|empty|class-free|without classes)\s*days?|days?\s*(?:off|free)|يوم(?:ين)?\s*(?:اجازة|إجازة|فاضي|فاضيين|اجازه)|ايام\s*(?:فاضية|اجازة)'
GOAL_WORDS = ('better schedule', 'better timetable', 'improve', 'optimi', 'more convenient', 'nicer', 'free day', 'days off', 'day off for',
              'fewer days', 'less days', 'compact', 'start later', 'no early', 'finish earlier', 'end earlier', 'finish by', 'end by',
              'fewer gaps', 'less gaps', 'no gaps', 'without gaps', 'جدول احسن', 'جدول أحسن', 'جدول افضل', 'جدول أفضل', 'حسن', 'اجازة', 'إجازة', 'فراغات')


def wants_improvement(text):
    return bool(re.search(FREE_DAY, text)) or any(w in text for w in GOAL_WORDS)


def goals_in(text, calendar):
    """{'free_days': n, 'start_after': hour, 'end_before': hour, 'gaps': True} from the message."""
    from app.assistant import hour
    from app.rule_parser import TIME
    goals = {}
    m = re.search(r'(\d|' + '|'.join(NUMBERS) + r')\s+(?:' + FREE_DAY + r')', text) or re.search(FREE_DAY, text)
    if m:
        word = m.group(1) if m.groups() and m.group(1) else 'a'
        goals['free_days'] = int(word) if word.isdigit() else NUMBERS.get(word, 1)
        if 'يومين' in m.group(0):
            goals['free_days'] = 2
    if re.search(r'fewer days|less days|compact|اقل ايام|أقل أيام', text):
        goals.setdefault('free_days', 1)
    when = re.search(r'(?:no (?:classes|lectures) before|start(?:ing)? (?:after|at|from)|not before|from|بعد|من)\s*(?:the\s+)?' + TIME, text)
    if when or re.search(r'start later|no early', text):
        goals['start_after'] = round(hour(when.groups()) * 2) / 2 if when else 10
    until = re.search(r'(?:finish(?:ed)? by|end(?:s)? by|no (?:classes|lectures) after|done by|until|قبل|لحد)\s*' + TIME, text)
    if until or re.search(r'finish earlier|end earlier', text):
        goals['end_before'] = round(hour(until.groups(), default_pm=True) * 2) / 2 if until else 14
    if re.search(r'gap|فراغ|idle|waiting', text):
        goals['gaps'] = True
    for key, limit in (('start_after', (calendar['start_hour'], calendar['end_hour'])), ('end_before', (calendar['start_hour'], calendar['end_hour']))):
        if key in goals and not limit[0] < goals[key] < limit[1]:
            goals.pop(key)
    return goals


def target_groups(text, view):
    """Groups named, else the group on screen, else the group the chat is about."""
    from app.assistant_courses import groups_in
    named = groups_in(text, view)
    if named:
        return named
    for g in [(view.get('screen') or {}).get('group'), *((view.get('memory') or {}).get('groups') or [])]:
        if g and any(r['id'] == g for r in view['records']):
            return [g]
    return []


def improve(slots, view, say):
    """Analyse the week, propose rules, and the regeneration that follows them."""
    from app.assistant import clock
    cal = view['calendar']
    records = {r['id']: r['data'] for r in view['records']}
    goals, groups = slots.get('goals') or {}, slots.get('groups') or []
    if not goals:
        return {'text': [say('What would make it better?', 'ما الذي يجعله أفضل؟')], 'asking': True,
                'choices': [{'label': say('Two free days', 'يومين إجازة'), 'text': 'two free days'}, {'label': say('One free day', 'يوم إجازة'), 'text': 'a free day'},
                            {'label': say('No classes before 10:00', 'لا محاضرات قبل 10'), 'text': 'no classes before 10:00'},
                            {'label': say('Finish by 14:00', 'الانتهاء قبل 2'), 'text': 'finish by 2pm'}, {'label': say('Fewer gaps', 'فراغات أقل'), 'text': 'fewer gaps'}]}
    if not groups:
        return {'text': [say('For which group or programme? For example "two free days for BA5-G7" or "for IT Security year 3".',
                             'لأي مجموعة أو برنامج؟ مثلاً "يومين إجازة لـ BA5-G7".')], 'asking': True}
    codes = ', '.join(records[g].get('code') for g in groups[:6]) + ('…' if len(groups) > 6 else '')
    days = cal['days']
    periods = cal.get('teaching_periods') or []
    per_day = len(periods) or max(1, (cal['end_hour'] - cal['start_hour']) * 60 // cal['period_minutes'])
    mine = {g: [s for s in view['sessions'] if g in s['groups']] for g in groups}
    lines, rules = [], []
    if 'free_days' in goals:
        want = goals['free_days']
        load = {d: sum(1 for g in groups for s in mine[g] if s['day'] == d) for d in days}
        free_now = [d for d in days if load[d] == 0]
        busiest = max((len(mine[g]) for g in groups), default=0)
        if len(days) - want < 1 or busiest > (len(days) - want) * per_day:
            return {'text': [say(f"{want} free days won't fit: {codes} need{'s' if len(groups) == 1 else ''} up to {busiest} sessions a week, and {len(days) - want} days hold {(len(days) - want) * per_day}.",
                                 f"{want} أيام إجازة لا تكفي: تحتاج {codes} حتى {busiest} محاضرة، و{len(days) - want} أيام تسع {(len(days) - want) * per_day}.")]}
        # The lightest days of the week become free; at the ends of the week first when equally light.
        edge = lambda d: min(days.index(d), len(days) - 1 - days.index(d))
        chosen = sorted(days, key=lambda d: (load[d] > 0, load[d], edge(d)))[:want]
        chosen = sorted(chosen, key=days.index)
        moved = sum(load[d] for d in chosen)
        now = say(f"Now {codes} {'has' if len(groups) == 1 else 'have'} {len(free_now)} free day{'s' if len(free_now) != 1 else ''}" + (f" ({', '.join(free_now)})" if free_now else '') + '.',
                  f"الآن لدى {codes} {len(free_now)} يوم إجازة" + (f" ({'، '.join(free_now)})" if free_now else '') + '.')
        lines.append(now)
        if len(free_now) >= want:
            lines.append(say(f"That is already {want} or more; I'll make sure {' and '.join(chosen)} stay free in every future timetable.",
                             f"هذا بالفعل {want} أو أكثر؛ سأضمن بقاء {' و'.join(chosen)} بدون محاضرات في الجداول القادمة."))
        else:
            lines.append(say(f"I'll keep {' and '.join(chosen)} free" + (f", moving the {moved} session(s) there to the other days" if moved else '') + '.',
                             f"سأجعل {' و'.join(chosen)} بدون محاضرات" + (f"، ونقل {moved} محاضرة منها لأيام أخرى" if moved else '') + '.'))
        for g in groups:
            for d in chosen:
                rules.append({'title': f"{records[g]['code']} free on {d}"[:100], 'type': 'group_unavailable', 'group_id': g, 'day': d,
                              'start_hour': cal['start_hour'], 'end_hour': cal['end_hour'], 'strength': 'mandatory'})
    if 'start_after' in goals:
        h = goals['start_after']
        early = sum(1 for g in groups for s in mine[g] if s['start_minute'] < h * 60)
        lines.append(say(f"No classes before {clock(int(h * 60))} on any day ({early} session(s) start earlier now).", f"لا محاضرات قبل {clock(int(h * 60))} ({early} محاضرة تبدأ أبكر الآن)."))
        rules += [{'title': f"{records[g]['code']} no classes before {clock(int(h * 60))}"[:100], 'type': 'group_unavailable', 'group_id': g, 'day': None,
                   'start_hour': cal['start_hour'], 'end_hour': h, 'strength': 'mandatory'} for g in groups]
    if 'end_before' in goals:
        h = goals['end_before']
        late = sum(1 for g in groups for s in mine[g] if s['end_minute'] > h * 60)
        lines.append(say(f"Finished by {clock(int(h * 60))} every day ({late} session(s) end later now).", f"الانتهاء قبل {clock(int(h * 60))} يومياً ({late} محاضرة تنتهي بعد ذلك الآن)."))
        rules += [{'title': f"{records[g]['code']} done by {clock(int(h * 60))}"[:100], 'type': 'group_unavailable', 'group_id': g, 'day': None,
                   'start_hour': h, 'end_hour': cal['end_hour'], 'strength': 'mandatory'} for g in groups]
    if 'start_after' in goals or 'end_before' in goals:
        lo = goals.get('start_after', cal['start_hour']) * 60
        hi = goals.get('end_before', cal['end_hour']) * 60
        fits = sum(1 for p in periods if p['start'] >= lo and p['end'] <= hi) if periods else int((hi - lo) // cal['period_minutes'])
        busiest = max((len(mine[g]) for g in groups), default=0)
        usable_days = len(days) - goals.get('free_days', 0)
        if fits * usable_days < busiest:
            return {'text': [say(f"That leaves {fits} period(s) a day on {usable_days} days ({fits * usable_days} in all), but {codes} need up to {busiest} sessions. Try a wider window.",
                                 f"يبقى {fits} فترة يومياً على {usable_days} أيام، لكن {codes} تحتاج حتى {busiest} محاضرة. جرّب نطاقاً أوسع.")]}
    if goals.get('gaps') and not rules:
        lines.append(say('I\'ll generate them again; the solver keeps students\' gaps between classes as small as it can.', 'سأنشئها مرة أخرى؛ المحلل يقلل الفراغات بين المحاضرات قدر الإمكان.'))
    steps = []
    for n, rule in enumerate(rules):
        steps.append({'method': 'POST', 'path': '/rules', 'body': rule, 'save_as': f'r{n}'})
        steps.append({'method': 'POST', 'path': f'/rules/$r{n}/approve', 'body': {}})
    scope = [{'programme': records[g]['major'], 'year': records[g].get('year'), 'group': g} for g in groups[:30]]
    generate = {'type': 'generate', 'scope': scope, 'label': say('Generate', 'إنشاء'),
                **({'base_run_id': view['published_id'], 'replace': True} if view.get('published_id') else {}),
                **({'filter': {'group': groups[0]}} if len(groups) == 1 else {})}
    lines.append(say(f"Then I'll generate {codes} again" + (' inside the published timetable, so everyone else keeps their week.' if view.get('published_id') else '.') +
                     (' These become rules you can remove later ("remove the rule for ' + records[groups[0]]['code'] + '").' if rules else ''),
                     f"ثم أنشئ {codes} مرة أخرى" + (' داخل الجدول المنشور، ويحتفظ الباقون بأسبوعهم.' if view.get('published_id') else '.') +
                     (' تصبح هذه قيوداً يمكن حذفها لاحقاً.' if rules else '')))
    if not steps:
        return {'text': lines, 'action': generate}
    return {'text': lines, 'action': {'type': 'apply_changes', 'steps': steps, 'then': generate, 'label': say('Apply and generate', 'تطبيق ثم إنشاء')}}
