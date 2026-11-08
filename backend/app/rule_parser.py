"""Deterministic English/Arabic interpreter for typed scheduling constraints.

It returns the same ProposalEnvelope shape as the GPT adapter, so its output goes through
the same validation, review, draft and approval steps. It never guesses: an unknown or
ambiguous name, a missing number or an unrecognised request becomes a clarification or an
"unsupported" code, and the request can then go to GPT (when configured) or be edited.
"""
import math
import re
import unicodedata

DAYS = {
    'sunday': 'Sunday', 'sun': 'Sunday', 'الأحد': 'Sunday', 'الاحد': 'Sunday', 'احد': 'Sunday',
    'monday': 'Monday', 'mon': 'Monday', 'الاثنين': 'Monday', 'الإثنين': 'Monday', 'اثنين': 'Monday',
    'tuesday': 'Tuesday', 'tue': 'Tuesday', 'tues': 'Tuesday', 'الثلاثاء': 'Tuesday', 'ثلاثاء': 'Tuesday',
    'wednesday': 'Wednesday', 'wed': 'Wednesday', 'الأربعاء': 'Wednesday', 'الاربعاء': 'Wednesday', 'اربعاء': 'Wednesday',
    'thursday': 'Thursday', 'thu': 'Thursday', 'thurs': 'Thursday', 'الخميس': 'Thursday', 'خميس': 'Thursday',
    'friday': 'Friday', 'fri': 'Friday', 'الجمعة': 'Friday', 'الجمعه': 'Friday', 'جمعة': 'Friday',
    'saturday': 'Saturday', 'sat': 'Saturday', 'السبت': 'Saturday', 'سبت': 'Saturday',
    # Egyptian spellings
    'الحد': 'Sunday', 'الاتنين': 'Monday', 'اتنين': 'Monday', 'التلات': 'Tuesday', 'تلات': 'Tuesday', 'التلاتاء': 'Tuesday',
    'الاربع': 'Wednesday', 'الأربع': 'Wednesday', 'الخميس': 'Thursday',
}
EVERY_DAY = ('every day', 'everyday', 'daily', 'each day', 'all days', 'any day', 'كل يوم', 'كل الأيام', 'كل الايام', 'يوميا', 'يومياً')
NEGATIVE = ("can't", 'cant', 'cannot', 'can not', 'not available', 'unavailable', 'no class', 'no classes', 'no lecture', 'no lectures',
            'not teach', "doesn't teach", "don't teach", 'not free', 'busy', 'off on', 'day off', 'avoid', 'not be scheduled', 'never',
            'not on', 'no teaching', 'closed', 'under maintenance', 'not usable', 'blocked',
            'لا يستطيع', 'لا تستطيع', 'لا يمكن', 'غير متاح', 'غير متاحة', 'مش فاضي', 'مش فاضية', 'مشغول', 'مشغولة', 'لا محاضرات',
            'مفيش محاضرات', 'بدون محاضرات', 'إجازة', 'اجازة', 'مغلق', 'مغلقة', 'لا يدرس', 'لا تدرس', 'ممنوع')
PREFER = ('prefer', 'prefers', 'would like', 'likes to', 'rather', 'ideally', 'يفضل', 'تفضل', 'يحب', 'تحب', 'يفضّل')
ONLY = ('only', 'just', 'must be on', 'must be between', 'فقط', 'بس')
SAME_DAY = ('not on the same day', 'not the same day', 'different days', 'separate days', 'same day', 'نفس اليوم', 'أيام مختلفة', 'ايام مختلفة')
ROOM_WORDS = ('in room', 'in the', 'room', 'lab ', 'hall', 'must be in', 'needs', 'held in', 'في قاعة', 'في معمل', 'قاعة', 'معمل', 'مدرج')
ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
TIME = r'(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.|ص|م|صباحا|صباحاً|مساء|مساءً|ظهرا|ظهراً)?'


def normalise(text):
    text = unicodedata.normalize('NFKC', text).translate(ARABIC_DIGITS).lower()
    text = re.sub('[إأآ]', 'ا', text).replace('ى', 'ي').replace('ـ', '')
    return re.sub(r'\s+', ' ', text).strip()


def plain(name):
    """Name without titles, for matching 'Dr. Ahmed Ali' against 'Ahmed Ali' or 'Dr Ahmed'."""
    name = normalise(name)
    name = re.sub(r'^(dr\.?|prof\.?|eng\.?|mr\.?|ms\.?|mrs\.?|ta|د\.?|م\.?|ا\.?د\.?|الدكتور|الدكتورة|دكتور|دكتورة|المهندس|المهندسة|الاستاذ|الاستاذة|استاذ|استاذة)\s+', '', name)
    return name.strip()


def mentions(text, phrase):
    if not phrase or len(phrase) < 2:
        return False
    return re.search(r'(?<![\w])' + re.escape(phrase) + r'(?![\w])', text) is not None


# Words that appear in many record names and never identify one on their own.
GENERIC = {'year', 'group', 'level', 'section', 'room', 'hall', 'lab', 'laboratory', 'lecture', 'tutorial', 'course', 'class',
           'the', 'and', 'for', 'computer', 'science', 'engineering', 'السنة', 'سنة', 'مجموعة', 'قاعة', 'معمل', 'مدرج', 'محاضرة', 'سكشن'}


ARABIC = re.compile('[\u0600-\u06ff]')
# Arabic letters by sound class; vowels and vowel-like letters (ا و ي ى ة ع ء) are dropped.
AR_SOUNDS = {'ب': 'b', 'ت': 't', 'ث': 't', 'ج': 'g', 'ح': 'h', 'خ': 'k', 'د': 'd', 'ذ': 'z', 'ر': 'r', 'ز': 'z', 'س': 's',
             'ش': 'S', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'غ': 'g', 'ف': 'f', 'ق': 'k', 'ك': 'k', 'ل': 'l', 'م': 'm',
             'ن': 'n', 'ه': 'h', 'پ': 'b', 'چ': 'g', 'ڤ': 'f', 'گ': 'g'}
LATIN_SOUNDS = {'b': 'b', 'p': 'b', 't': 't', 'g': 'g', 'j': 'g', 'h': 'h', 'k': 'k', 'q': 'k', 'c': 'k', 'd': 'd', 'z': 'z',
                'r': 'r', 's': 's', 'f': 'f', 'v': 'f', 'l': 'l', 'm': 'm', 'n': 'n', 'x': 'ks'}
AR_VARIANTS = {'ث': {'t', 's'}, 'ذ': {'z', 'd'}, 'ظ': {'z', 'd'}, 'ق': {'k', ''}}
# Two-letter Latin spellings of one Arabic sound; both readings are tried ("Fathy" is t + h).
DIGRAPHS = {'sh': 'S', 'kh': 'k', 'gh': 'g', 'th': 't', 'dh': 'z'}
# Words of the request language that are never names.
AR_STOP = {'من', 'الى', 'الي', 'لحد', 'لغاية', 'بعد', 'قبل', 'يوم', 'ايام', 'في', 'على', 'علي', 'بين', 'لا', 'مش', 'الساعة', 'الساعه', 'ساعة',
           'التدريس', 'يدرس', 'تدرس', 'تستطيع', 'يستطيع', 'يمكن', 'فاضي', 'فاضية', 'فاضيه', 'متاح', 'متاحة', 'غير', 'كل', 'الظهر', 'الصبح',
           'صباحا', 'مساء', 'العصر', 'محاضرات', 'محاضرة', 'سكشن', 'معمل', 'قاعة', 'مدرج', 'مجموعة', 'السنة', 'سنة', 'الدكتور', 'الدكتورة',
           'دكتور', 'دكتورة', 'د', 'م', 'استاذ', 'استاذة', 'المهندس', 'المهندسة', 'مشغول', 'مشغولة', 'اجازة', 'مغلق', 'مغلقة', 'يفضل',
           'تفضل', 'يحب', 'تحب', 'فقط', 'بس', 'و', 'او', 'هو', 'هي', 'اللي', 'عند', 'عنده', 'عندها', 'ممنوع', 'بدون', 'مفيش', 'نفس', 'مختلفة',
           # everyday words that sound like names (احسن ~ Hassan, افضل ~ Fadl, كويس ~ Kways)
           'احسن', 'افضل', 'اكتر', 'اكثر', 'اقل', 'كويس', 'كويسة', 'عايز', 'عايزة', 'عايزين', 'نريد', 'نحتاج', 'محتاج', 'محتاجين', 'الجدول',
           'جدول', 'يبقى', 'يبقي', 'تبقى', 'خلي', 'خليه', 'ممكن', 'لو', 'سمحت', 'شكرا', 'الطلاب', 'الطلبة', 'المعيد', 'المعيدة', 'معيد', 'معيدة',
           'الاسبوع', 'اسبوع', 'النهارده', 'بكره', 'دايما', 'ابدا', 'خالص', 'كمان', 'برضه', 'حاجة', 'حصة', 'حصص', 'الحصة', 'المادة', 'مادة'}


def sounds(word):
    """Consonant skeletons of a word, Arabic or Latin: 'صالح' -> {'slh'}, 'Saleh' -> {'slh'}."""
    word = normalise(word)
    if ARABIC.search(word):
        found = {''}
        for ch in word:
            # Egyptian and classical readings: عثمان is Osman or Othman.
            options = AR_VARIANTS.get(ch, {AR_SOUNDS.get(ch, '')})
            found = {f + o for f in found for o in options}
        return found
    word = re.sub('[^a-z]', '', word)
    found = {''}
    i = 0
    while i < len(word):
        pair = word[i:i + 2]
        if pair in DIGRAPHS:
            single = LATIN_SOUNDS.get(word[i], '') + LATIN_SOUNDS.get(word[i + 1], '')
            found = {f + DIGRAPHS[pair] for f in found} | {f + single for f in found}
            i += 2
            continue
        found = {f + LATIN_SOUNDS.get(word[i], '') for f in found}
        i += 1
    # Doubled letters are written once in Arabic ("Fattah" / فتاح).
    return {re.sub(r'(.)\1+', r'\1', f) for f in found}


def close(a, b):
    """Same skeleton, or (for longer words) one letter apart."""
    if a == b:
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def sounds_alike(word, part):
    return any(close(x, y) for x in sounds(word) for y in sounds(part) if x and y)


def name_words(text):
    """Arabic words of the request that could be part of a name (titles and request words removed)."""
    words = [w.strip('.,،؛:!?()') for w in text.split()]
    return [w for w in words if ARABIC.search(w) and w not in AR_STOP and len(w) >= 2]


def spoken_matches(text, records, kind):
    """Records whose Latin name is written in Arabic in the text: full names, then single distinctive words."""
    words = name_words(text)
    if not words:
        return {}, {}
    full, single = {}, {}
    for r in records:
        if r['kind'] != kind:
            continue
        name = plain(r.get('data', r)['name'])
        if ARABIC.search(name):
            continue  # Arabic names already match directly
        parts = [p for p in name.split() if p not in GENERIC]
        if len(parts) > 1 and any(all(sounds_alike(words[i + k], parts[k]) for k in range(len(parts))) for i in range(len(words) - len(parts) + 1)):
            full[r['id']] = r
        for part in parts:
            if len(part) >= 3 and max(map(len, sounds(part))) >= 2 and any(len(w) >= 3 and sounds_alike(w, part) for w in words):
                single.setdefault(part, []).append(r)
    return full, single


def find_records(text, records, kind):
    """Records of `kind` named in the text by code, full name, or a distinctive part of the name."""
    found = {}
    for r in records:
        if r['kind'] != kind:
            continue
        data = r.get('data', r)
        names = {normalise(data['code']), normalise(data['name']), plain(data['name'])}
        if any(mentions(text, n) for n in names):
            found[r['id']] = r
    spoken, spoken_parts = spoken_matches(text, records, kind) if kind == 'instructors' else ({}, {})
    found.update(spoken)
    if found:
        return list(found.values()), []
    # Single-word matches ("Ahmed") only count when they pick exactly one record.
    partial = {part: list(rows) for part, rows in spoken_parts.items()}
    for r in records:
        if r['kind'] != kind:
            continue
        for part in plain(r.get('data', r)['name']).split():
            if len(part) >= 3 and part not in GENERIC and mentions(text, part):
                partial.setdefault(part, []).append(r)
    ambiguous = [part for part, rows in partial.items() if len({x['id'] for x in rows}) > 1]
    unique = {rows[0]['id']: rows[0] for part, rows in partial.items() if len({x['id'] for x in rows}) == 1}
    return list(unique.values()), ambiguous


def hour(match, default_pm=False):
    h, m, suffix = int(match[0]), int(match[1] or 0), (match[2] or '').replace('.', '')
    if suffix in ('pm', 'م', 'مساء', 'مساءً', 'ظهرا', 'ظهراً') and h < 12:
        h += 12
    elif suffix in ('am', 'ص', 'صباحا', 'صباحاً') and h == 12:
        h = 0
    elif not suffix and (h < 8 or default_pm and h < 12):
        h += 12  # "after 2" in a teaching day means 14:00
    return h + m / 60


def times(text, calendar):
    """(start_hour, end_hour) the text restricts to, or None for the whole teaching day."""
    first, last = calendar['start_hour'], calendar['end_hour']
    span = re.search(r'(?:between|from|بين|من)\s*' + TIME + r'\s*(?:and|to|till|until|-|–|الى|إلى|لحد|لغاية|و)\s*' + TIME, text)
    if span:
        groups = span.groups()
        return hour(groups[:3]), hour(groups[3:], default_pm=hour(groups[:3]) >= 12)
    span = re.search(TIME + r'\s*(?:-|–|to)\s*' + TIME, text)
    if span:
        groups = span.groups()
        return hour(groups[:3]), hour(groups[3:])
    before = re.search(r'(?:before|until|till|earlier than|قبل|لحد)\s*(?:الساعة\s*)?' + TIME, text)
    if before:
        return first, hour(before.groups())
    after = re.search(r'(?:after|later than|from|starting|بعد|من)\s*(?:الساعة\s*)?' + TIME, text)
    if after:
        return hour(after.groups()), last
    if any(w in text for w in ('morning', 'mornings', 'صباح', 'الصبح', 'صباحا')):
        return first, 12
    if any(w in text for w in ('afternoon', 'evening', 'بعد الظهر', 'العصر', 'مساء', 'بالليل')):
        return 12, last
    return None


def days_in(text, calendar):
    if any(phrase in text for phrase in EVERY_DAY):
        return [None]
    found = []
    for word, day in DAYS.items():
        if mentions(text, normalise(word)) and day not in found:
            found.append(day)
    return found


def number(text, unit_words):
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:' + '|'.join(unit_words) + ')', text)
    return float(match.group(1)) if match else None


def round_half(value):
    return round(value * 2) / 2


def floor_half(value):
    return math.floor(value * 2) / 2


def ceil_half(value):
    return math.ceil(value * 2) / 2


def parse(text, context):
    """context = {'records': [{'id','kind','data'}], 'calendar': {'days','start_hour','end_hour'}}."""
    records, calendar = context['records'], context['calendar']
    raw = text
    text = normalise(text)
    title = raw.strip()[:100] or 'Typed constraint'
    proposals, clarify, unsupported = [], [], []

    def outside(day, start, end):
        """Intervals of the teaching week outside (day, start, end); day None = every day."""
        first, last = calendar['start_hour'], calendar['end_hour']
        pieces = [(day, first, start)] if start > first else []
        pieces += [(day, end, last)] if end < last else []
        if day is not None:
            pieces += [(d, first, last) for d in calendar['days'] if d != day]
        if not pieces:
            clarify.append('nothing_left_in_the_week')
        return pieces

    def rule(**fields):
        body = {'title': title, 'instructor_id': None, 'room_id': None, 'group_id': None, 'activity_id': None,
                'day': None, 'start_hour': None, 'end_hour': None, 'strength': 'mandatory',
                'params': {'room_ids': None, 'activity_ids': None, 'hours': None, 'days': None}}
        body.update(fields)
        proposals.append({'kind': 'rule', 'data': body})

    instructors, amb_i = find_records(text, records, 'instructors')
    groups, amb_g = find_records(text, records, 'groups')
    rooms, amb_r = find_records(text, records, 'rooms')
    activities, amb_a = find_records(text, records, 'courses')
    year = re.search(r'(?:year|level|السنة|سنة|الفرقة|فرقة|المستوى)\s*(\d+)', text)
    if year and not groups:
        groups = [r for r in records if r['kind'] == 'groups' and r.get('data', r).get('year') == int(year.group(1))]
        if not groups:
            clarify.append(f'no_groups_in_year_{year.group(1)}')
    ambiguous = amb_i + amb_g + amb_r + amb_a
    for word in ambiguous:
        clarify.append(f'ambiguous_name:{word}')
    for kind_word, kind in (('lab', 'lab'), ('معمل', 'lab'), ('tutorial', 'tutorial'), ('سكشن', 'tutorial'), ('lecture', 'lecture'), ('محاضرة', 'lecture')):
        if mentions(text, kind_word) and any(a.get('data', a)['activity_type'] == kind for a in activities):
            activities = [a for a in activities if a.get('data', a)['activity_type'] == kind]
            break
    days = days_in(text, calendar)
    window = times(text, calendar)
    # Rules store half-hours. A closure is rounded outwards (until 15:15 blocks to 15:30) and an
    # allowed or preferred window inwards, so no session can fall inside a time that was ruled out.
    blocked = allowed = None
    if window:
        clip = lambda a, b: (max(calendar['start_hour'], a), min(calendar['end_hour'], b))
        blocked = clip(floor_half(window[0]), ceil_half(window[1]))
        allowed = clip(ceil_half(window[0]), floor_half(window[1]))
        if allowed[0] >= allowed[1] and blocked[0] >= blocked[1]:
            clarify.append('time_outside_teaching_hours')
        window = blocked
    whole_day = (calendar['start_hour'], calendar['end_hour'])
    daily_hours = number(text, [r'hours?\s*(?:a|per|each)?\s*day', r'hrs?\s*(?:a|per)?\s*day', r'ساعات?\s*(?:في|ف)?\s*اليوم', r'ساعة\s*(?:في|ف)?\s*اليوم', r'ساعات يوميا'])
    week_days = number(text, [r'days?\s*(?:a|per|each)?\s*week', r'teaching days', r'أيام\s*(?:في|ف)?\s*الأسبوع', r'ايام\s*(?:في|ف)?\s*الاسبوع', r'ايام'])

    if daily_hours is not None:
        targets = [('instructor_max_daily_hours', 'instructor_id', r) for r in instructors] + [('group_max_daily_hours', 'group_id', r) for r in groups]
        if not targets and not ambiguous:
            clarify.append('missing_target')
        for type_, field, target in targets:
            rule(type=type_, **{field: target['id']}, params={'room_ids': None, 'activity_ids': None, 'hours': round_half(daily_hours), 'days': None})
    elif week_days is not None and instructors and not groups:
        for target in instructors:
            rule(type='instructor_max_days', instructor_id=target['id'], params={'room_ids': None, 'activity_ids': None, 'hours': None, 'days': int(week_days)})
    elif any(p in text for p in SAME_DAY):
        if len(activities) < 2:
            clarify.append('need_two_activities')
        else:
            rule(type='activities_not_same_day', params={'room_ids': None, 'activity_ids': [a['id'] for a in activities][:10], 'hours': None, 'days': None})
    elif activities and rooms and any(w in text for w in ROOM_WORDS) and not any(p in text for p in NEGATIVE):
        for activity in activities:
            rule(type='activity_room', activity_id=activity['id'], params={'room_ids': [r['id'] for r in rooms][:20], 'activity_ids': None, 'hours': None, 'days': None})
    else:
        negative = any(normalise(p) in text for p in NEGATIVE)
        prefer = any(normalise(p) in text for p in PREFER)
        only = any(normalise(p) in text for p in ONLY)
        if not (negative or prefer or only or days or window):
            unsupported.append('unrecognised_request')
        elif not (instructors or groups or rooms or activities):
            if not ambiguous:
                clarify.append('missing_target')
        elif not days and not window:
            clarify.append('missing_day_or_time')
        else:
            start, end = window or whole_day
            inner = allowed or whole_day  # for allowed and preferred windows
            for day in days or [None]:
                if prefer and not negative:
                    for target in instructors:
                        rule(type='preferred_period', instructor_id=target['id'], day=day, start_hour=inner[0], end_hour=inner[1], strength='preferred')
                    if not instructors:
                        unsupported.append('preferences_need_an_instructor')
                elif negative:
                    for target in instructors:
                        rule(type='unavailable', instructor_id=target['id'], day=day, start_hour=start, end_hour=end)
                    for target in groups:
                        rule(type='group_unavailable', group_id=target['id'], day=day, start_hour=start, end_hour=end)
                    for target in rooms:
                        rule(type='room_unavailable', room_id=target['id'], day=day, start_hour=start, end_hour=end)
                    if activities and not (instructors or groups or rooms):
                        # "No ML lectures on Sunday mornings": allow the activity everywhere else.
                        for activity in activities:
                            for d, s0, e0 in outside(day, start, end):
                                rule(type='activity_allowed', activity_id=activity['id'], day=d, start_hour=s0, end_hour=e0)
                else:
                    for target in activities:
                        rule(type='activity_allowed', activity_id=target['id'], day=day, start_hour=inner[0], end_hour=inner[1])
                    for target in groups if not activities else []:
                        rule(type='group_allowed', group_id=target['id'], day=day, start_hour=inner[0], end_hour=inner[1])
                    if instructors and not (activities or groups):
                        # "Dr. X teaches only on Monday mornings": unavailable everywhere else.
                        for target in instructors:
                            for d, s0, e0 in outside(day, *inner):
                                rule(type='unavailable', instructor_id=target['id'], day=d, start_hour=s0, end_hour=e0)
    # Drop duplicates (for example an every-day preference added once per loop).
    unique, seen = [], set()
    for p in proposals:
        key = repr(sorted((k, repr(v)) for k, v in p['data'].items() if k != 'title'))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    proposals = unique[:50]
    clarify = list(dict.fromkeys(clarify))[:50]
    unsupported = list(dict.fromkeys(unsupported))[:50]
    if proposals and not clarify and not unsupported:
        decision = 'ready'
    elif clarify:
        decision = 'conflict' if proposals else 'clarify'
    elif unsupported:
        decision = 'mixed' if proposals else 'unsupported'
    else:
        decision, unsupported = 'unsupported', ['unrecognised_request']
    return {'decision': decision, 'proposals': proposals, 'clarifications': clarify, 'unsupported': unsupported}
