"""The exam timetable as landscape A4 pages, one per exam day, built on the server.

Browser printing can turn a landscape layout sideways and names the file after the
window; a generated file has real landscape pages and a short descriptive name.
"""
from collections import defaultdict
from datetime import date
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

LOGO = Path(__file__).resolve().parents[2] / 'frontend' / 'public' / 'giu-schedule-logo.png'
FACULTY_ORDER = ['ENGINEERING', 'INFORMATICS', 'BUSINESS INFORMATICS', 'BUSINESS ADMINISTRATION', 'PHE/BIO', 'PHYSICAL THERAPY']
PALETTE = ['#b6dde3', '#c7eac2', '#c9bcd7', '#fbd79e', '#b9cde3', '#f3c5c5', '#c9e7e1', '#f5e89f']
INK, MUTED, HEAD = colors.HexColor('#244c3e'), colors.HexColor('#627469'), colors.HexColor('#e8eee0')


def colour(program):
    """The same colour as the browser view for a programme."""
    h = 0
    for ch in program:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    h = h - (1 << 32) if h & 0x80000000 else h
    return colors.HexColor(PALETTE[abs(h) % len(PALETTE)])


def matches(exam, query):
    """The page's search box: course code, name or programme."""
    text = f"{exam['course_code']} {exam['course_name']} {' '.join(p.get('program_or_cohort') or '' for p in exam['programs'])}"
    return query.lower() in text.lower()


def short_name(settings, query=''):
    """'Midterm Exams 20-31 Oct 2026', or with a search: 'Midterm Exams 20-31 Oct 2026 - INCS'."""
    start, end = date.fromisoformat(settings['start_date']), date.fromisoformat(settings['end_date'])
    if (start.year, start.month) == (end.year, end.month):
        span = f"{start.day}-{end.day} {end:%b %Y}"
    elif start.year == end.year:
        span = f"{start.day} {start:%b}-{end.day} {end:%b %Y}"
    else:
        span = f"{start:%d %b %Y}-{end:%d %b %Y}"
    name = f'Midterm Exams {span}'
    clean = ''.join(ch for ch in query if ch.isalnum() or ch in ' -')[:30].strip()
    return f'{name} - {clean}' if clean else name


def exam_pdf(run, query='', published=False, stale=False):
    snapshot, exams = run.snapshot, [a for a in run.result['assignments'] if matches(a, query)]
    slots = [tuple(s) for s in snapshot.get('slots') or [('09:00', '11:00'), ('11:15', '13:15'), ('13:30', '15:30')]]
    title = short_name(snapshot['settings'], query)
    out = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(out, pagesize=page, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=10 * mm, bottomMargin=12 * mm,
                            title=title, author='JadwAI')
    small = ParagraphStyle('cell', fontName='Helvetica', fontSize=7, leading=8.6, textColor=INK)
    head = ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=INK)
    note = ParagraphStyle('note', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=MUTED)
    status = 'Published' if published else 'DRAFT'
    story = []
    days = sorted({a['date'] for a in exams})
    if not days:
        story.append(Paragraph(escape(title), head))
        story.append(Paragraph('No exams match this search.', note))
    usable = page[0] - 24 * mm
    slot_w = usable / len(slots)
    for n, day in enumerate(days):
        todays = [a for a in exams if a['date'] == day]
        faculty = lambda p: p.get('faculty_section') or 'OTHER'
        sections = sorted({faculty(p) for a in todays for p in a['programs']} | ({'OTHER'} if any(not a['programs'] for a in todays) else set()),
                          key=lambda f: (FACULTY_ORDER.index(f) if f in FACULTY_ORDER else 99, f))
        logo = Image(str(LOGO), width=34 * mm, height=12 * mm, kind='proportional') if LOGO.exists() else Spacer(1, 1)
        weekday = date.fromisoformat(day).strftime('%A, %B %-d, %Y')
        heading = Table([[logo, Paragraph(f'{escape(day[:4])} Mid Term Exams Schedule <font color="#627469" size="11">({status})</font>'
                                          f'<br/><font size="11">{escape(weekday)}</font>', head)]],
                        colWidths=[40 * mm, usable - 40 * mm])
        heading.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
        story += [heading, Spacer(1, 3 * mm)]
        rows = [[Paragraph(f'<b>{s}-{e}</b>', small) for s, e in slots]]
        style = [('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd3c5')), ('BACKGROUND', (0, 0), (-1, 0), HEAD),
                 ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('FONTSIZE', (0, 0), (-1, -1), 7)]
        for section in sections:
            rows.append([Paragraph(f'<b>{escape(section)}</b>', small)] + [''] * (len(slots) - 1))
            style += [('SPAN', (0, len(rows) - 1), (-1, len(rows) - 1)), ('BACKGROUND', (0, len(rows) - 1), (-1, len(rows) - 1), colors.HexColor('#f4f6ef'))]
            per_slot = []
            for s, _ in slots:
                entries = []
                for a in (x for x in todays if x['start_time'] == s):
                    progs = [p for p in a['programs'] if faculty(p) == section]
                    if not a['programs'] and section == 'OTHER':
                        progs = [None]
                    for p in progs:
                        entries.append((a, p))
                per_slot.append(entries)
            for i in range(max((len(e) for e in per_slot), default=0)):
                row = []
                for j, entries in enumerate(per_slot):
                    if i >= len(entries):
                        row.append('')
                        continue
                    a, p = entries[i]
                    program = (p or {}).get('program_or_cohort') or ''
                    semester = (p or {}).get('semester')
                    halls = a.get('halls') or []
                    text = (f"GIU-Cairo.{escape(program)} {semester or ''}{' Semester' if semester else ''} - " if program else '') + \
                           f"<b>{escape(a['course_name'])}</b> {escape(a['course_code'])}"
                    if halls:
                        text += '<br/><font color="#4a5d52">' + escape(f"{a.get('students') or ''} students · " + ', '.join(
                            f"{h['room_code']}" + (f" ({h['invigilator_name']})" if h.get('invigilator_name') else '') for h in halls)) + '</font>'
                    row.append(Paragraph(text, small))
                    if program:
                        style.append(('BACKGROUND', (j, len(rows)), (j, len(rows)), colour(program)))
                rows.append(row)
        table = Table(rows, colWidths=[slot_w] * len(slots), repeatRows=1)
        table.setStyle(TableStyle(style))
        story += [table, Spacer(1, 3 * mm)]
        footer = ('Published exam timetable.' if published else 'Draft: not yet published.') + \
                 (' Halls and invigilators as assigned in this draft.' if any(a.get('halls') for a in todays) else ' Dates and times only; no halls assigned.') + \
                 (' Inputs have changed since this draft was made.' if stale else '') + (f' Filtered by "{query}".' if query else '')
        story.append(Paragraph(escape(footer), note))
        if n < len(days) - 1:
            story.append(PageBreak())
    doc.build(story)
    return out.getvalue(), title
