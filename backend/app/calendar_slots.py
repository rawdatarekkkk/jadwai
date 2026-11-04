"""Where a session of a given teaching duration may sit within one day.

With named teaching periods, a session covers one or more consecutive periods whose
teaching minutes add up exactly to its duration (for example a three-hour lab over two
90-minute periods). Short breaks between those periods stay inside the session; a break
longer than MAX_INNER_BREAK ends the run, so sessions never straddle lunch-length gaps.
Without named periods, sessions start on the period grid and run continuously.
"""
MAX_INNER_BREAK = 30


def day_placements(calendar, duration):
    """List of (start_minute, end_minute, covered_period_indices) within one day."""
    periods = calendar.get('teaching_periods') or []
    if not periods:
        first, last, step = calendar['start_hour'] * 60, calendar['end_hour'] * 60, calendar['period_minutes']
        return [(s, s + duration, ()) for s in range(first, last - duration + 1, step)]
    found = []
    for i, period in enumerate(periods):
        taught, covered = 0, []
        for j in range(i, len(periods)):
            if j > i and periods[j]['start'] - periods[j - 1]['end'] > MAX_INNER_BREAK:
                break
            taught += periods[j]['end'] - periods[j]['start']
            covered.append(j)
            if taught >= duration:
                break
        if taught == duration:
            found.append((period['start'], periods[covered[-1]]['end'], tuple(covered)))
    return found


def placement_for(calendar, duration, start, end):
    """The matching placement, or None when (start, end) is not a valid session slot."""
    return next((p for p in day_placements(calendar, duration) if (p[0], p[1]) == (start, end)), None)


def end_for(calendar, duration, start):
    """End minute of the session starting at `start`, or None if it cannot start there."""
    return next((p[1] for p in day_placements(calendar, duration) if p[0] == start), None)


def day_slots(calendar):
    """The day's atomic teaching slots: named periods, or grid cells without them."""
    periods = calendar.get('teaching_periods') or []
    if periods:
        return [(p['start'], p['end']) for p in periods]
    first, last, step = calendar['start_hour'] * 60, calendar['end_hour'] * 60, calendar['period_minutes']
    return [(s, s + step) for s in range(first, last, step)]


def slots_in(calendar, start, end):
    """Indices of the day's slots occupied by a session from start to end."""
    return tuple(i for i, (s, e) in enumerate(day_slots(calendar)) if start <= s and e <= end)
