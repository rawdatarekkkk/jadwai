"""Compact, on-demand PDF summary with vector charts; no browser or external service."""
from io import BytesIO
from html import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

INK = HexColor('#244c3e')
MUTED = HexColor('#627469')
GREEN = HexColor('#39745c')
PALE = HexColor('#edf3ed')
LINE = HexColor('#dce5dc')
AMBER = HexColor('#ad793b')


def pdf_report(run_id, snapshot, stats, stale):
    out = BytesIO()
    c = canvas.Canvas(out, pagesize=A4, pageCompression=1)
    c.setTitle('JadwAI - Schedule summary')
    c.setAuthor('JadwAI')
    width, height = A4
    left, right = 42, width - 42
    usable = right - left

    def text(x, y, value, size=10, bold=False, color=INK):
        c.setFillColor(color)
        c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        c.drawString(x, y, str(value))

    def paragraph(x, top, value, w=usable, size=9, color=MUTED):
        style = ParagraphStyle('report', fontName='Helvetica', fontSize=size,
                               leading=size * 1.4, textColor=color)
        p = Paragraph(escape(str(value)), style)
        _, h = p.wrap(w, 200)
        p.drawOn(c, x, top - h)
        return h

    def line(y):
        c.setStrokeColor(LINE)
        c.line(left, y, right, y)

    def percent(v):
        return '-' if v is None else f'{v:.1f}%'

    def bar(x, y, w, fraction, color=GREEN):
        c.setFillColor(PALE)
        c.roundRect(x, y, w, 9, 4, fill=1, stroke=0)
        if fraction is not None and fraction > 0:
            c.setFillColor(color)
            c.roundRect(x, y, max(1, min(1, fraction) * w), 9, 4, fill=1, stroke=0)

    coverage, validation = stats['coverage'], stats['validation']
    preferences, usage = stats['preferences'], stats['utilization']
    scope = (stats.get('scope') or {}).get('label')
    week = stats.get('week') or {}
    scored = bool(preferences['applicable_sessions'])  # preference rules apply to these sessions
    text(left, 800, 'JadwAI', 21, True)
    text(right - 128, 802, 'SCHEDULE REPORT', 9, True, MUTED)
    text(left, 768, 'Your timetable at a glance', 24, True)
    heading = f"{scope or 'Full schedule'} | Input version {stats['input_version']} | DRAFT - UNPUBLISHED"
    from reportlab.pdfbase.pdfmetrics import stringWidth
    text(left, 746, heading, max(6, min(10, 10 * usable / stringWidth(heading, 'Helvetica', 10))), color=MUTED)  # long group names shrink to fit
    if stale:
        c.setFillColor(HexColor('#fff0d9'))
        c.roundRect(left, 699, usable, 30, 5, fill=1, stroke=0)
        paragraph(left + 10, 721, 'Inputs have changed. This report describes the saved schedule, not the current inputs.', usable - 20, 9, AMBER)
    else:
        text(left, 710, 'Figures cover the sessions these groups attend; validation and overlaps cover the whole timetable.' if scope else 'The whole timetable. Choose a year, programme or group on the Timetable page for its own report.', 9, color=MUTED)

    card_w = (usable - 20) / 3
    cards = [
        ('Sessions scheduled', f"{coverage['scheduled_sessions']} / {coverage['expected_sessions']}", f"{coverage['unscheduled_sessions']} unscheduled"),
        ('Supported validation', 'Passed' if validation['passed'] else 'Failed', f"{len(validation['checks'])} checks evaluated"),
        ('Preferences satisfied', percent(preferences['satisfaction_percent']), f"{preferences['satisfied_sessions']} / {preferences['applicable_sessions']} sessions with preferences")
        if scored else ('Free periods between classes', str(week.get('student_gaps', 0)), (f"{week.get('student_days', 0)} days on campus" if week.get('groups') == 1 else f"{week.get('days_per_group', 0):g} days on campus per group")),
    ]
    for i, (label, value, note) in enumerate(cards):
        x = left + i * (card_w + 10)
        c.setFillColor(PALE)
        c.roundRect(x, 608, card_w, 77, 7, fill=1, stroke=0)
        text(x + 12, 665, label, 9, color=MUTED)
        text(x + 12, 639, value, 23, True)
        text(x + 12, 622, note, 8, color=MUTED)

    text(left, 584, 'Sessions by day', 13, True)
    text(right - 92, 584, 'Unit: sessions', 8, color=MUTED)
    days = stats['per_day']
    maximum = max((d['sessions'] for d in days), default=0)
    step = min(23, 137 / max(1, len(days)))
    for i, day in enumerate(days):
        y = 559 - i * step
        text(left, y, day['day'], 9)
        bar(left + 78, y - 1, usable - 115, day['sessions'] / maximum if maximum else 0)
        text(right - 22, y, day['sessions'], 9, True)
    text(left, 410, 'Overlap pairs', 10, True)
    conflicts = validation.get('conflicts')
    counts = 'Not evaluated' if conflicts is None else f"Rooms: {conflicts['room_overlap_pairs']}     Instructors: {conflicts['instructor_overlap_pairs']}     Student groups: {conflicts['group_overlap_pairs']}"
    text(left + 92, 410, counts, 9)
    line(396)

    comfort = stats.get('convenience') or {}
    if scored:
        text(left, 374, 'Teaching preferences', 13, True)
        fraction = preferences['satisfied_sessions'] / preferences['applicable_sessions']
        bar(left, 351, usable, fraction)
        text(left, 335, f"Satisfied: {preferences['satisfied_sessions']}   |   Not satisfied: {preferences['unsatisfied_sessions']}", 9)
        text(left, 317, f"Rules: {preferences['fully_satisfied_rules']} fully met, {preferences['partially_satisfied_rules']} partly met, {preferences['unsatisfied_rules']} unmet.", 9, color=MUTED)
    else:
        text(left, 374, 'Week quality', 13, True)
        text(left, 350, f"Free periods between classes: {week.get('student_gaps', 0)}   |   Days on campus: {week.get('student_days', 0)}{'' if week.get('groups') == 1 else f" ({week.get('days_per_group', 0):g} per group)"}   |   Longest day: {week.get('longest_day_hours', 0):g} h", 9)
        text(left, 334, f"Sessions in the first or last period: {week.get('edge_sessions', 0)}" + (f"   |   Instructor free periods between classes: {comfort['instructor_gaps']}" if 'instructor_gaps' in comfort else ''), 9)
        text(left, 317, 'Lower is better. Counted from the saved assignments' + (' for these groups.' if scope else ' for all student groups.'), 9, color=MUTED)
    line(302)

    text(left, 280, 'Resource use', 13, True)
    for y, label, value in [(255, 'Student week filled with teaching', usage['group_week_percent']) if scope else (255, 'Available room time used', usage['room_time_percent']),
                            (226, 'Seats filled during scheduled sessions', usage['occupied_room_seat_percent'])]:
        text(left, y, label, 9)
        bar(left + 245, y - 1, usable - 298, None if value is None else value / 100)
        text(right - 40, y, percent(value), 9, True)
    advising = stats.get('advising') or {}
    students = f"   |   Advising students: {advising['students']}, {advising['students_with_clashes']} with clashes" if advising.get('students') else ''
    resources = f"Rooms used: {usage['rooms_used']}   |   Instructors teaching: {usage['instructors_used']}" if scope else f"Rooms used: {usage['rooms_used']} / {usage['rooms_total']}   |   Instructors used: {usage['instructors_used']} / {usage['instructors_total']}"
    text(left, 207, resources + students, 9, color=MUTED)
    line(193)

    realism = stats['validation'].get('realism')
    daily_note = 'Daily policy was not checked for this saved report.'
    if realism:
        p = realism['policy']
        hours = lambda v: 'no limit' if v is None else f'{v:g} h'
        periods = lambda v, what: f'no {what} limit' if v is None else f'at most {v} {what}'
        daily_note = f"Daily policy checked: students {hours(p.get('student_daily_hours'))}; instructors {hours(p.get('instructor_daily_hours'))}; {periods(p.get('max_consecutive_periods'), 'consecutive periods')}; {periods(p.get('max_idle_periods'), 'idle periods')}."
    text(left, 174, 'How to read this report', 10, True)
    notes = [
        'Preferences count each session once if its instructor has an approved preferred window.' if scored else 'Free periods are empty teaching periods between two classes on the same day; days on campus count each group-day with teaching.',
        ('Student week filled: teaching hours over the teaching week, excluding breaks.' if scope else 'Room time uses all saved rooms and teaching periods, excluding breaks.') + ' Seat use counts attending students, including advising students, against room capacity. Low use alone does not mean a poor timetable.',
        ('Weekly maxima: ' + str(sum(r.get('weekly_limit_configured', False) for r in stats['per_instructor'])) + '/' + str(len(stats['per_instructor'])) + ' instructors configured. ' + daily_note + ' Missing weekly maxima remain unchecked. Approved locks are checked only when recorded in the saved validation. Draft only; not publication-ready.') if 'workload' in stats['validation'] else 'Weekly maxima were not recorded for this saved report. Daily limits and locks apply only when recorded in the saved validation. Draft only; not publication-ready.',
    ]
    if snapshot['calendar'].get('weekly_load_policy', {}).get('allow_overtime'):
        extra = sum(r.get('extra_hours') or 0 for r in stats['per_instructor'])
        notes[-1] = f'Standard load: 12 teaching hours per instructor per week. Hours above 12 are extra time, not violations. Total extra time: {extra:g} hours. ' + daily_note + ' Draft only; not publication-ready.'
    top = 160
    for note in notes:
        top -= paragraph(left, top, note, size=8) + 5
    seconds = stats['solver']['seconds']
    solver = 'Not recorded' if seconds is None else f'{seconds:g} s'
    text(left, 59, f"Solver: {solver} | Optimal for selected objective: {'yes' if stats['solver']['optimal_for_supported_objective'] else 'not proven'}", 8, color=MUTED)
    text(left, 43, f'Run: {run_id}', 7, color=MUTED)
    text(left, 30, f"Statistics saved: {stats['generated_at'][:19].replace('T', ' ')} UTC", 7, color=MUTED)
    text(right - 35, 43, '1 / 1', 8, color=MUTED)
    c.showPage()
    c.save()
    return out.getvalue()
