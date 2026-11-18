"""Teaching positions: doctors teach lectures; TAs teach tutorials and labs."""
REQUIRED = {'lecture': 'doctor', 'tutorial': 'ta', 'lab': 'ta'}


def position_conflict(activity_type, instructor):
    """True when a classified instructor holds the wrong position for this activity type.

    Instructors saved before positions existed stay unclassified and are reported
    by input checks instead of being rejected here."""
    position = (instructor or {}).get('position')
    return position is not None and position != REQUIRED[activity_type]


def unassigned_tas(instructors, activities):
    """TAs not yet named for any course's tutorials or labs (for example just added).

    They can't be given teaching, so the every-TA-must-teach rule waits until they are
    assigned to a course; input checks list them as a warning instead of blocking."""
    named = {t for a in activities for t in a.get('eligible_instructors', [])}
    return [r for r in instructors if r.get('position') == 'ta' and r['id'] not in named]


def tas_without_teaching(instructors, activities):
    """TA ids that cannot each get an activity of their own (one teacher per activity).

    A bipartite matching, so it also catches pools with more TAs than activities.
    TAs named for no activity at all are left to unassigned_tas."""
    named = {t for a in activities for t in a.get('eligible_instructors', [])}
    tas = [r['id'] for r in instructors if r.get('position') == 'ta' and r['id'] in named]
    eligible = {ta: [a['id'] for a in activities if ta in a['eligible_instructors']] for ta in tas}
    holder = {}

    def place(ta, seen):
        for activity in eligible[ta]:
            if activity not in seen:
                seen.add(activity)
                if activity not in holder or place(holder[activity], seen):
                    holder[activity] = ta
                    return True
        return False

    return [ta for ta in tas if not place(ta, set())]
