"""Teaching positions: doctors teach lectures; TAs teach tutorials and labs."""
REQUIRED = {'lecture': 'doctor', 'tutorial': 'ta', 'lab': 'ta'}


def position_conflict(activity_type, instructor):
    """True when a classified instructor holds the wrong position for this activity type.

    Instructors saved before positions existed stay unclassified and are reported
    by input checks instead of being rejected here."""
    position = (instructor or {}).get('position')
    return position is not None and position != REQUIRED[activity_type]


def tas_without_teaching(instructors, activities):
    """TA ids that cannot each get an activity of their own (one teacher per activity).

    A bipartite matching, so it also catches pools with more TAs than activities."""
    tas = [r['id'] for r in instructors if r.get('position') == 'ta']
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
