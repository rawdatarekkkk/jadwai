"""Who may use a room. A room with no reservation is open to every activity; a reserved
special room (for example a Data Science Lab) only to activities of its programmes or
catalogue courses. One rule for the solver, validator, input checks, locks and edits."""


def reserved(room):
    return bool(room.get('reserved_majors') or room.get('reserved_course_ids'))


def room_allows(room, activity, records):
    """records: id -> record (groups are looked up for their programme)."""
    if not reserved(room):
        return True
    if activity.get('course_id') and activity['course_id'] in (room.get('reserved_course_ids') or []):
        return True
    majors = set(room.get('reserved_majors') or [])
    return any((records.get(g) or {}).get('major') in majors for g in activity.get('group_ids', []))
