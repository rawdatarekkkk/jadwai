"""Teaching positions: doctors teach lectures; TAs teach tutorials and labs."""
REQUIRED = {'lecture': 'doctor', 'tutorial': 'ta', 'lab': 'ta'}


def position_conflict(activity_type, instructor):
    """True when a classified instructor holds the wrong position for this activity type.

    Instructors saved before positions existed stay unclassified and are reported
    by input checks instead of being rejected here."""
    position = (instructor or {}).get('position')
    return position is not None and position != REQUIRED[activity_type]
