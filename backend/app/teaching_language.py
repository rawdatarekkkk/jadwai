"""Compile a local model's semantic frame into validated global teaching windows.

The model reads natural language; calendar arithmetic and rule construction stay in code.
This module never saves a proposal or rule.
"""
import math
import re

FRAME = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'kind': {'type': 'string', 'enum': ['teaching_window', 'other', 'clarify']},
        'activity_types': {'type': 'array', 'items': {'type': 'string', 'enum': ['lecture', 'tutorial', 'lab']}},
        'strength': {'type': 'string', 'enum': ['mandatory', 'preferred', 'unknown']},
        'mode': {'type': 'string', 'enum': ['avoid', 'within', 'unknown']},
        'days': {'type': 'array', 'items': {'type': 'string', 'enum': ['Saturday','Sunday','Monday','Tuesday','Wednesday','Thursday','Friday']}},
        'slot_number': {'type': ['integer', 'null']},
        'start_hour': {'type': ['number', 'null']},
        'end_hour': {'type': ['number', 'null']},
        'question': {'type': 'string'},
    },
    'required': ['kind','activity_types','strength','mode','days','slot_number','start_hour','end_hour','question'],
}
INSTRUCTION = """Read the user's English or Arabic timetable requirement into the supplied semantic frame. Do not generate database rules or do calendar arithmetic.
Use teaching_window ONLY for time restrictions/preferences applying to generic teaching types. If a person, room, named course, programme or group is targeted, or the request is about ordering, workload or another policy, use other.
activity_types: lectures means [lecture] ONLY; tutorials/sections means [tutorial]; labs means [lab]; classes/teaching means all three. Never widen a specific type.
strength: preferred/ideally/if possible/avoid if possible means preferred (soft), even if the phrase contains 'no'. Must/cannot/required/no without a soft qualifier means mandatory. Ask when unclear.
mode: avoid for a time to avoid, including 'preferred: no ...'; within for times to use. 'Not before T' avoids the time before T; 'not after T' avoids after T. Do not invert avoid into within.
For an ordinal slot/period, put its number in slot_number and leave start/end null. The application resolves its times. First means 1, second 2, etc. Do NOT call the first slot ambiguous; it is the first configured teaching period. days=[] means every teaching day. For explicit clock times use decimal hours; before T has null start and end=T, after T has start=T and null end. Do not invent a time for vague 'early' or 'late'.
Use clarify with a focused question if required information is absent. Return a short complete frame only."""


def eligible(text):
    return bool(re.search(r'\b(?:lectures?|tutorials?|labs?|classes|teaching|periods?|slots?)\b|محاضر|سكشن|سكاشن|معامل|حصص|فتر', text, re.I))


def clarification(question):
    return {'decision':'clarify','proposals':[],'clarifications':[question or 'Please specify the teaching time and whether this is mandatory or preferred.'],'unsupported':[]}


def compile_frame(frame, text, calendar):
    if frame.get('kind') == 'other':
        return None
    if frame.get('kind') != 'teaching_window':
        return clarification(frame.get('question'))
    kinds = frame.get('activity_types')
    strength, mode = frame.get('strength'), frame.get('mode')
    if not isinstance(kinds,list) or not kinds or set(kinds)-{'lecture','tutorial','lab'} or strength not in ('mandatory','preferred') or mode not in ('avoid','within'):
        return clarification(frame.get('question'))
    # Explicit top-level strength is user intent, not a model guess.
    if re.match(r'^\s*(?:preferred|preferably|ideally|soft(?: constraint)?|if possible)\b',text,re.I):
        if re.search(r'\b(?:must|required|mandatory)\b',text,re.I):
            return clarification('Please separate the mandatory requirements from the preferences.')
        strength='preferred'
    if re.match(r'^\s*(?:mandatory|required|hard(?: constraint)?|must)\b',text,re.I):
        strength='mandatory'
    first,last=calendar['start_hour'],calendar['end_hour']
    slot = frame.get('slot_number')
    if slot is not None:
        if type(slot) is not int or slot < 1:
            return clarification('Which teaching slot do you mean?')
        periods=calendar.get('teaching_periods') or []
        if periods:
            if slot > len(periods):return clarification('That slot is outside the configured teaching day.')
            start,end=periods[slot-1]['start']/60,periods[slot-1]['end']/60
        else:
            if not calendar.get('period_minutes'):return clarification('Configure the teaching periods before referring to a slot.')
            start=first+(slot-1)*calendar['period_minutes']/60
            end=start+calendar['period_minutes']/60
    else:
        start=frame.get('start_hour');end=frame.get('end_hour')
        if start is None and end is None:return clarification(frame.get('question'))
        start=first if start is None else start
        end=last if end is None else end
    if not all(type(value) in (float,int) and math.isfinite(value) for value in (start,end)) or not first <= start < end <= last:
        return clarification('Please give a time range inside the configured teaching day.')
    days=frame.get('days') or []
    if not isinstance(days,list) or any(day not in calendar['days'] for day in days):
        return clarification('Which configured teaching days should this apply to?')
    # A window applies to the whole week; unaffected days need explicit full-day alternatives.
    target_days = list(dict.fromkeys(days)) if days else [None]
    windows=[]
    for day in target_days:
        if mode=='within':windows.append((day,start,end))
        else:
            if start>first:windows.append((day,first,start))
            if end<last:windows.append((day,end,last))
    if days:
        windows += [(day,first,last) for day in calendar['days'] if day not in days]
    periods = calendar.get('teaching_periods') or []
    if periods:
        windows = [(day, start, end) for day, start, end in windows if any(start * 60 <= period['start'] and period['end'] <= end * 60 for period in periods)]
    if not windows:return clarification('That would leave no teaching time. Which time should remain available?')
    # Existing rules encode half hours. Do not silently change a named slot boundary.
    if any(value*2 != round(value*2) for _,start,end in windows for value in (start,end)):
        return clarification('This exact slot boundary cannot be represented by the current half-hour rule grid. Please choose an aligned time.')
    proposals=[]
    for day,start,end in windows:
        proposals.append({'kind':'rule','data':{'title':text.strip()[:100],'type':'teaching_preferred' if strength=='preferred' else 'teaching_allowed',
            'instructor_id':None,'room_id':None,'group_id':None,'activity_id':None,'strength':strength,'day':day,'start_hour':float(start),'end_hour':float(end),
            'params':{'activity_types':list(dict.fromkeys(kinds)),'room_ids':None,'activity_ids':None,'hours':None,'days':None}}})
    return {'decision':'ready','proposals':proposals,'clarifications':[],'unsupported':[]}
