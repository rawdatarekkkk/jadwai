"""Exam Save as PDF: real landscape pages, one per day, short name, search filter."""
import io
import types
import pypdf
from app.exam_pdf import exam_pdf, short_name


def run(exams):
    return types.SimpleNamespace(snapshot={'settings': {'start_date': '2026-10-20', 'end_date': '2026-10-31'},
                                           'slots': [['09:00', '11:00'], ['11:15', '13:15'], ['13:30', '15:30']]},
                                 result={'assignments': exams})


def exam(code, day='2026-10-20', start='09:00', faculty='INFORMATICS', program='CS'):
    return {'course_code': code, 'course_name': f'Course {code}', 'date': day, 'start_time': start, 'students': 100,
            'programs': [{'program_or_cohort': program, 'semester': 3, 'faculty_section': faculty}],
            'halls': [{'room_code': 'A.020', 'capacity': 260, 'invigilator_name': 'Laila Kamel'}]}


def test_landscape_pages_per_day_and_a_short_name():
    pdf, name = exam_pdf(run([exam('CS1'), exam('CS2', day='2026-10-21'), exam('BA1', faculty='BUSINESS ADMINISTRATION', program='BA')]))
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    assert name == 'Midterm Exams 20-31 Oct 2026' and len(reader.pages) == 2
    page = reader.pages[0]
    assert float(page.mediabox.width) > float(page.mediabox.height) and not page.get('/Rotate')
    text = page.extract_text()
    assert 'Tuesday, October 20, 2026' in text and 'INFORMATICS' in text and 'BUSINESS ADMINISTRATION' in text and 'A.020 (Laila Kamel)' in text


def test_search_filters_exams_and_names_the_file():
    pdf, name = exam_pdf(run([exam('INCS101'), exam('BA1', program='BA')]), 'INCS')
    assert name == 'Midterm Exams 20-31 Oct 2026 - INCS'
    text = pypdf.PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert 'INCS101' in text and 'BA1' not in text


def test_a_long_day_continues_on_the_next_page():
    pdf, _ = exam_pdf(run([exam(f'C{i}', start=['09:00', '11:15', '13:30'][i % 3]) for i in range(150)]))
    assert len(pypdf.PdfReader(io.BytesIO(pdf)).pages) > 1


def test_names_across_months():
    assert short_name({'start_date': '2026-12-27', 'end_date': '2027-01-07'}) == 'Midterm Exams 27 Dec 2026-07 Jan 2027'
    assert short_name({'start_date': '2026-10-28', 'end_date': '2026-11-06'}) == 'Midterm Exams 28 Oct-6 Nov 2026'


def test_finals_with_second_chance_midterms_and_quiz_rounds_are_titled_by_what_they_hold():
    makeup = {**exam('C1'), 'exam_type': 'makeup', 'label': 'Second-chance midterm', 'duration_minutes': 120, 'start_time': '09:00', 'end_time': '11:00'}
    final = {**exam('C1', start='11:30'), 'exam_type': 'final', 'label': 'Final', 'duration_minutes': 180, 'end_time': '14:30'}
    pdf, name = exam_pdf(run([makeup, final]))
    assert name == 'Final Exams 20-31 Oct 2026'
    text = pypdf.PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert '2026 Final Exams Schedule' in text and '09:00-11:00' in text and 'Second-chance midterm' in text and '11:30-14:30' in text
    assert text.index('09:00-11:00') < text.index('11:30-14:30')  # in time order
    quiz = {**exam('Q1'), 'exam_type': 'quiz', 'label': 'Quiz 2', 'duration_minutes': 30, 'end_time': '09:30'}
    assert exam_pdf(run([quiz]))[1] == 'Quiz 2 20-31 Oct 2026'
