"""The weekly timetable as a landscape A4 PDF, built on the server.

Printing from a browser cannot set the file name everywhere, and some print paths turn a
landscape layout sideways on a portrait sheet. A generated file has a real landscape page
and a short, descriptive name such as "BA Y3 G7 Schedule.pdf".
"""
import re
from io import BytesIO
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from app.calendar_slots import day_slots, slots_in

INK, MUTED, LINE = HexColor('#244c3e'), HexColor('#627469'), HexColor('#cbd3c5')
HEAD, DAY, CARD, CARD_EDGE = HexColor('#eef2e8'), HexColor('#e8eee0'), HexColor('#f1f5ea'), HexColor('#9baa91')
ORDINALS = ['First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth', 'Ninth', 'Tenth']
SMALL_WORDS = {'and', 'of', 'the', 'for', 'in', '&'}


def initials(name):
    """'Business Administration' -> 'BA'; 'Finance, Banking & Accounting' -> 'FBA'."""
    words = [w for w in re.split(r'[\s,/&-]+', name or '') if w and w.lower() not in SMALL_WORDS]
    return ''.join(w[0].upper() for w in words) or (name or '')[:3]


def group_short(group):
    """The group's own number, e.g. 'G7' from 'Business Administration Core G7'."""
    for text in (group.get('name') or '', group.get('code') or ''):
        found = re.findall(r'\bG\d+\b', text, re.I)
        if found:
            return found[-1].upper()
    return group.get('code') or group.get('name') or 'Group'


def short_name(snapshot, scope):
    """A short, descriptive file name: 'BA Y3 G7 Schedule', 'BA Y3 Schedule', 'Full Schedule'."""
    records = {r['id']: r for r in snapshot['records']}
    if scope and scope.get('group') in records:
        g = records[scope['group']]
        parts = [initials(g.get('major')) if g.get('major') else '', f"Y{g['year']}" if g.get('year') else '', group_short(g)]
    elif scope:
        year, major = scope.get('year'), scope.get('major')
        parts = [initials(major) if major and major != '__unassigned' else '', f'Y{year}' if year and year != 'unassigned' else '']
    else:
        parts = ['Full']
    return ' '.join(p for p in parts if p) + ' Schedule'


def compact_groups(codes):
    """['BA5-G1', 'BA5-G2', 'BA5-G3', 'BA5-G5'] -> 'BA5-G1–G3, BA5-G5'."""
    numbered, other = {}, []
    for code in codes:
        m = re.fullmatch(r'(.*?)(G)(\d+)', code or '', re.I)
        if m:
            numbered.setdefault(m.group(1), []).append(int(m.group(3)))
        elif code:
            other.append(code)
    parts = []
    for prefix, numbers in numbered.items():
        numbers = sorted(set(numbers))
        start = prev = numbers[0]
        for n in numbers[1:] + [None]:
            if n is not None and n == prev + 1:
                prev = n
                continue
            parts.append(f'{prefix}G{start}' + (f'–G{prev}' if prev > start + 1 else f', {prefix}G{prev}' if prev == start + 1 else ''))
            if n is not None:
                start = prev = n
    return ', '.join(parts + other)


def fit(text, font, size, width):
    text = str(text)
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + '…', font, size) > width:
        text = text[:-1]
    return text.rstrip() + '…'


def clock(minute):
    return f'{minute // 60:02d}:{minute % 60:02d}'


def timetable_pdf(snapshot, assignments, title, subtitle):
    records = {r['id']: r for r in snapshot['records']}
    cal = snapshot['calendar']
    slots = day_slots(cal)
    out = BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(out, pagesize=(width, height), pageCompression=1)
    c.setTitle(title)
    c.setAuthor('JadwAI')
    left, right, top, bottom = 28, width - 28, height - 28, 30
    day_w = 64
    col_w = (right - left - day_w) / max(1, len(slots))
    lane_h, pad = 50, 3
    page = [1]

    def text(x, y, value, size=8, bold=False, color=INK):
        c.setFillColor(color)
        c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        c.drawString(x, y, str(value))

    def page_header(first):
        y = top
        if first:
            text(left, y - 18, 'JadwAI', 20, True)
            text(left + 90, y - 10, f"{snapshot['term']} · {snapshot['name']}", 9, color=MUTED)
            text(left + 90, y - 24, title, 13, True)
            text(left, y - 40, subtitle, 8, color=MUTED)
            y -= 52
        else:
            text(left, y - 10, f'{title} (continued)', 9, True)
            y -= 18
        # Column headings: periods with their times.
        c.setFillColor(HEAD)
        c.rect(left, y - 26, right - left, 26, fill=1, stroke=0)
        text(left + 6, y - 16, 'Day', 8, True)
        for i, (s, e) in enumerate(slots):
            x = left + day_w + i * col_w
            name = f'{ORDINALS[i]} Period' if cal.get('teaching_periods') and i < len(ORDINALS) else ''
            text(x + 5, y - 11, name or clock(s), 8, True)
            text(x + 5, y - 21, f'{clock(s)}–{clock(e)}', 7, color=MUTED)
        c.setStrokeColor(LINE)
        c.rect(left, y - 26, right - left, 26, fill=0, stroke=1)
        return y - 26

    def footer():
        text(left, 16, f'JadwAI · {title}', 6.5, color=MUTED)
        text(right - 30, 16, f'{page[0]}', 7, color=MUTED)

    y = page_header(True)
    for day in cal['days']:
        todays = sorted((a for a in assignments if a['day'] == day), key=lambda a: (a['start_minute'], a['end_minute']))
        # Lanes: each session goes in the first lane whose periods it covers are free.
        lanes = []
        for a in todays:
            cols = slots_in(cal, a['start_minute'], a['end_minute']) or (min(range(len(slots)), key=lambda i: abs(slots[i][0] - a['start_minute'])),)
            for lane in lanes:
                if not lane['used'] & set(cols):
                    break
            else:
                lane = {'used': set(), 'items': []}
                lanes.append(lane)
            lane['used'] |= set(cols)
            lane['items'].append((a, cols))
        chunks = [lanes[i:i + 8] for i in range(0, len(lanes), 8)] or [[]]
        for n, chunk in enumerate(chunks):
            row_h = max(22, len(chunk) * lane_h + pad)
            if y - row_h < bottom:
                footer(); c.showPage(); page[0] += 1
                y = page_header(False)
            c.setFillColor(DAY)
            c.rect(left, y - row_h, day_w, row_h, fill=1, stroke=0)
            text(left + 6, y - row_h / 2 - 3, day + (' (cont.)' if n else ''), 8, True)
            c.setStrokeColor(LINE)
            c.rect(left, y - row_h, right - left, row_h, fill=0, stroke=1)
            for i in range(1, len(slots)):
                c.line(left + day_w + i * col_w, y, left + day_w + i * col_w, y - row_h)
            if not chunk:
                for i in range(len(slots)):
                    text(left + day_w + i * col_w + col_w / 2 - 8, y - 14, 'Free', 8, color=MUTED)
            busy = set().union(*(lane['used'] for lane in chunk)) if chunk else set()
            for i in range(len(slots)):
                if chunk and i not in busy:
                    text(left + day_w + i * col_w + col_w / 2 - 8, y - 14, 'Free', 8, color=MUTED)
            for k, lane in enumerate(chunk):
                for a, cols in lane['items']:
                    act = records.get(a['activity_id'], {})
                    x = left + day_w + cols[0] * col_w + 2
                    w = len(cols) * col_w - 4
                    top_y = y - pad - k * lane_h
                    c.setFillColor(CARD); c.setStrokeColor(CARD_EDGE)
                    c.roundRect(x, top_y - lane_h + pad, w, lane_h - pad, 2, fill=1, stroke=1)
                    tx, tw = x + 3, w - 6
                    groups = [records.get(g, {}).get('code') or '' for g in act.get('group_ids', [])]
                    lines = [
                        (f"{clock(a['start_minute'])}–{clock(a['end_minute'])} · {(act.get('activity_type') or '').title()}", 6.3, False, MUTED),
                        (act.get('name') or act.get('code') or '', 7.5, True, INK),
                        (f"{act.get('code') or ''} · {records.get(a['room_id'], {}).get('code') or records.get(a['room_id'], {}).get('name') or ''}", 6.3, False, INK),
                        (records.get(a['instructor_id'], {}).get('name') or '', 6.3, False, INK),
                        (compact_groups(groups), 6, False, MUTED),
                    ]
                    for j, (value, size, bold, color) in enumerate(lines):
                        text(tx, top_y - 9 - j * 8.6, fit(value, 'Helvetica-Bold' if bold else 'Helvetica', size, tw), size, bold, color)
            y -= row_h
    footer()
    c.showPage()
    c.save()
    return out.getvalue()
