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


ADVISING = ['Code', 'Name', 'Home group', 'Drop courses', 'Add courses', 'Check']


def with_advising(tmp_path, students, groups=None):
    """The basic workbook plus a second group and an Advising students sheet."""
    from openpyxl import load_workbook
    path = workbook(tmp_path, [course(Streams='Data Science')])
    wb = load_workbook(path)
    for g in groups or [['G2', 'Informatics and Computer Science', 5, 3, 'Data Science', 2, 25, '']]:
        wb['Groups'].append(g)
    ws = wb.create_sheet('Advising students'); ws.append(ADVISING); ws.append(['EXAMPLE'] + [''] * 5)
    for s in students:
        ws.append(s)
    wb.save(path)
    return path


def test_advising_students_are_checked_against_groups_and_courses(tmp_path):
    good = ['S-1', 'Omar Hamed', 'G1', 'ICS504', 'ICS504@G2', '']  # section change: same course, other group
    plan, problems = importer.check(with_advising(tmp_path, [good]), CALENDAR)
    assert problems == [] and plan['advising'] == [{'row': 3, 'code': 'S-1', 'name': 'Omar Hamed', 'home': 'G1', 'drops': ['ICS504'], 'adds': [('ICS504', 'G2')]}]
    bad = [['S-2', 'No Group', 'G9', 'ICS504', '', ''],
           ['S-3', 'Not Taken', 'G1', 'XYZ1', '', ''],
           ['S-4', 'Twice', 'G1', '', 'ICS504@G2', ''],
           ['S-5', 'No Group Given', 'G1', 'ICS504', 'ICS504', ''],
           ['S-6', 'Nothing', 'G1', '', '', '']]
    _, problems = importer.check(with_advising(tmp_path, bad), CALENDAR)
    text = '\n'.join(problems)
    assert 'row 3: home group G9 is not on the Groups sheet' in text
    assert 'row 4: dropped course XYZ1 is not on the Courses sheet' in text
    assert 'row 5: G1 already takes ICS504; drop it too to take it with G2' in text
    assert 'row 6: write the added course as COURSE@GROUP (ICS504@...)' in text
    assert 'row 7: list at least one dropped or added course' in text


def test_workbooks_without_the_advising_sheet_still_import(tmp_path):
    plan, problems = importer.check(workbook(tmp_path, [course()]), CALENDAR)
    assert problems == [] and plan['advising'] == []


def test_import_creates_new_advising_students_and_updates_existing_ones():
    class FakeApi:
        def __init__(self): self.calls = []
        def get(self, path): return {'students': [{'id': 'old-1', 'code': 'S-OLD'}]}
        def write(self, method, path, body, what): self.calls.append((method, path, body)); return {'id': 'x'}
    api = FakeApi()
    students = [{'code': 'S-NEW', 'name': 'New', 'home': 'G1', 'drops': ['ICS504'], 'adds': [('ICS504', 'G2')]},
                {'code': 's-old', 'name': 'Old', 'home': 'G2', 'drops': [], 'adds': [('ML', 'G1')]}]
    assert importer.commit_advising(students, {'G1': 'g1', 'G2': 'g2'}, {'ICS504': 'c1', 'ML': 'c2'}, api) == 2
    (m1, p1, b1), (m2, p2, b2) = api.calls
    assert (m1, p1) == ('POST', '/advising-students') and b1['changes'] == [
        {'action': 'drop', 'course_id': 'c1', 'group_id': None}, {'action': 'add', 'course_id': 'c1', 'group_id': 'g2'}]
    assert (m2, p2) == ('PUT', '/advising-students/old-1') and b2['group_id'] == 'g2'
