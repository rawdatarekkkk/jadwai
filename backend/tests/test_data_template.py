import importlib.util
from pathlib import Path
from openpyxl import Workbook

spec = importlib.util.spec_from_file_location('import_data_template', Path(__file__).resolve().parents[2] / 'scripts' / 'import_data_template.py')
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)
CALENDAR = {'teaching_periods': [{'start': 510, 'end': 600}, {'start': 615, 'end': 705}], 'start_hour': 8, 'end_hour': 18, 'period_minutes': 30}
HEADERS = {
    'Rooms': ['Code', 'Name', 'Capacity', 'Uses', 'Features', 'Check'],
    'Staff': ['Code', 'Name', 'Department', 'Position', 'Day off', 'Check'],
    'Groups': ['Code', 'Programme', 'Semester', 'Year', 'Stream', 'Group', 'Students', 'Check'],
    'Courses': ['Code', 'Name', 'Programme', 'Semester', 'Streams', 'Lectures/week', 'Tutorials/week', 'Labs/week', 'Minutes',
                'Doctors', 'TAs', 'Room features', 'Expected students', 'Workbook blocks', 'Check'],
}


def workbook(tmp_path, courses, staff=None):
    wb = Workbook(); wb.remove(wb.active)
    data = {
        'Rooms': [['R1', 'Hall', 200, 'lecture|exam_hall', '', ''], ['L1', 'Lab', 30, 'lab', 'Data Science Lab', '']],
        'Staff': staff or [['D1', 'Dr. One', 'CS', 'doctor', 'Friday', ''], ['T1', 'TA One', 'CS', 'ta', 'Sunday', '']],
        'Groups': [['G1', 'Informatics and Computer Science', 5, 3, 'Data Science', 1, 25, '']],
        'Courses': courses,
    }
    for name, headers in HEADERS.items():
        ws = wb.create_sheet(name); ws.append(headers)
        ws.append(['EXAMPLE'] + [''] * (len(headers) - 1))  # example rows are always skipped
        for row in data[name]:
            ws.append(row)
    path = tmp_path / 'filled.xlsx'; wb.save(path)
    return path


def course(**changes):
    row = dict(zip(HEADERS['Courses'], ['ICS504', 'Machine Learning', 'Informatics and Computer Science', 5, 'Data Science', 1, 0, 1, 90, 'D1', 'T1', 'Data Science Lab', None, 3, '']))
    row.update(changes)
    return [row[h] for h in HEADERS['Courses']]


def test_valid_workbook_plans_lectures_per_stream_and_labs_per_group(tmp_path):
    plan, problems = importer.check(workbook(tmp_path, [course()]), CALENDAR)
    assert problems == []
    assert plan['courses'][0]['streams'] == {'Data Science': ['G1']}
    assert plan['staff']['T1']['position'] == 'ta'


def test_problems_are_reported_by_sheet_and_row(tmp_path):
    rows = [course(Streams='Nope'), course(Code='ICS505', Doctors='T1', TAs='D1', **{'Room features': 'Workshop', 'Minutes': 75})]
    _, problems = importer.check(workbook(tmp_path, rows), CALENDAR)
    text = '\n'.join(problems)
    assert 'Courses row 3: unknown stream(s): Nope' in text
    assert 'Courses row 4: T1 is not a doctor' in text and 'D1 is not a TA' in text
    assert 'no lab room has all of: Workshop' in text
    assert '75 minutes does not fit the teaching periods' in text


def test_every_ta_must_teach(tmp_path):
    staff = [['D1', 'Dr. One', 'CS', 'doctor', 'Friday', ''], ['T1', 'TA One', 'CS', 'ta', 'Sunday', ''], ['T2', 'Idle TA', 'CS', 'ta', 'Monday', '']]
    _, problems = importer.check(workbook(tmp_path, [course()], staff), CALENDAR)
    assert problems == ['Staff: TA T2 (Idle TA) is not listed for any tutorial or lab. Every TA must teach.']
