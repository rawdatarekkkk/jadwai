"""Everyday questions JAI answers without the local model."""
from app.assistant_basics import basic_answer, priority_answer
from app.assistant_records import record_kind

VIEW = {
    'records': [
        {'id': 'r1', 'kind': 'rooms', 'data': {'code': 'C.101', 'capacity': 30, 'room_types': ['lab'], 'equipment': ['Computers', 'GPU']}},
        {'id': 'r2', 'kind': 'rooms', 'data': {'code': 'A3.020', 'capacity': 260, 'room_types': ['lecture', 'exam_hall'], 'equipment': ['Projector']}},
        {'id': 'i1', 'kind': 'instructors', 'data': {'name': 'Dr. Sara Hassan'}},
        {'id': 'g1', 'kind': 'groups', 'data': {'code': 'G1', 'size': 25}},
        {'id': 'g2', 'kind': 'groups', 'data': {'code': 'G2', 'size': 20}},
        {'id': 'c1', 'kind': 'courses', 'data': {'name': 'Math'}},
    ],
    'rules': [{'id': 'x', 'status': 'approved'}, {'id': 'y', 'status': 'draft'}],
    'published_id': None, 'run': None,
}


def text(q, ar=False, view=VIEW):
    reply = basic_answer(q, view, ar)
    return ' | '.join(reply['text']) if reply else None


def test_counts_in_english_and_egyptian_arabic():
    assert text('How many rooms do we have?') == '2 rooms.'
    assert text('how many labs') == '1 lab.'
    assert text('How many instructors are there') == '1 instructor.'
    assert text('how many students') == '45 students in 2 student groups.'
    assert text('How many rules?').startswith('2 rules: 1 approved, 1 waiting')
    assert text('كام قاعة عندنا؟', ar=True) == '2 قاعة.'
    assert text('كام دكتور عندنا', ar=True) == '1 مدرس.'


def test_lists_rooms_by_type():
    assert text('list the labs') == '1 lab: | • C.101 · 30 seats · GPU'
    assert 'A3.020' in text('show me the exam halls')


def test_greetings_thanks_and_publication():
    assert text('hello').startswith('Hello!')
    assert text('thanks') == "You're welcome."
    assert text('شكرا', ar=True) == 'العفو.'
    assert text('Is the timetable published?').startswith('No teaching timetable is published')
    published = {**VIEW, 'published_id': 'run1', 'run': {'name': 'Fall', 'published': True, 'stale': True}}
    reply = text('Is the timetable published?', view=published)
    assert reply.startswith('Yes, a teaching timetable is published: Fall') and 'inputs have changed' in reply


def test_leaves_everything_else_to_the_other_routes():
    for q in ('When does Dr. Sara Hassan teach?', 'Generate a new timetable', 'hello, can you move G1 to Monday?', 'Which rooms are free on Sunday at 10?'):
        assert basic_answer(q, VIEW, False) is None, q


def test_a_rule_request_is_not_a_new_record():
    assert record_kind("add a rule: dr. sara hassan can't teach on monday") is None
    assert record_kind('add an instructor') == 'instructors'


def early(q, memory=None, ar=False):
    reply = priority_answer(q, VIEW, ar, memory)
    return reply and ' | '.join(reply['text'])


def test_special_rooms_and_room_features_come_before_free_room_questions():
    assert early('and how many are special rooms') == '1 room with special equipment: | • C.101 · 30 seats · GPU'
    assert early('how many special labs do we have').startswith('1 lab with special equipment')
    features = early('what are the features available')
    assert features.startswith('Room equipment recorded') and '• GPU: C.101' in features and '• Projector: A3.020' in features
    assert early('ايه الأجهزة الموجودة في القاعات', ar=True).startswith('تجهيزات القاعات')
    # A day or time makes it an availability question for the other routes.
    assert early('which rooms with a GPU are free on Sunday at 10') is None
    assert early('how many rooms do we have') is None


def test_what_are_they_lists_what_was_just_counted():
    assert basic_answer('how many instructors', VIEW, False)['listed'] == 'instructors'
    assert early('what are they', {'listed': 'instructors'}) == '1 instructor: | • Dr. Sara Hassan'
    assert early('ايه هي', {'listed': 'labs'}, ar=True).startswith('1 معمل')
    assert early('what are they', {}) is None
