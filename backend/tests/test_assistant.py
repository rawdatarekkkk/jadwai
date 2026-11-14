import asyncio
import json
import httpx
from app.assistant import ARABIC, answer, find_dates, model_understand, understand
from datetime import date

CAL = {'days': ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday'], 'start_hour': 8, 'end_hour': 18, 'period_minutes': 90,
       'teaching_periods': [{'start': 510, 'end': 600}, {'start': 615, 'end': 705}, {'start': 720, 'end': 810}]}
RECORDS = [
    {'id': 'r1', 'kind': 'rooms', 'data': {'name': 'A3.128', 'code': 'A3.128', 'capacity': 60, 'room_types': ['lecture']}},
    {'id': 'r2', 'kind': 'rooms', 'data': {'name': 'C.101', 'code': 'C.101', 'capacity': 30, 'room_types': ['lab']}},
    {'id': 'r3', 'kind': 'rooms', 'data': {'name': 'C.102', 'code': 'C.102', 'capacity': 20, 'room_types': ['lab']}},
    {'id': 'i1', 'kind': 'instructors', 'data': {'name': 'Dr. Mohamed Fawzy', 'code': 'MF', 'department': 'Informatics'}},
    {'id': 'g7', 'kind': 'groups', 'data': {'name': 'Business Administration III G7', 'code': 'BA5-G7', 'major': 'Business Administration', 'year': 3}},
    {'id': 'g8', 'kind': 'groups', 'data': {'name': 'IT Security I G1', 'code': 'ITS1-G1', 'major': 'IT Security', 'year': 1}},
    {'id': 'c1', 'kind': 'courses', 'data': {'name': 'Management Accounting', 'code': 'BUAD301', 'group_ids': ['g7']}},
]
SESSIONS = [{'activity_id': 'c1', 'day': 'Sunday', 'start_minute': 510, 'end_minute': 600, 'room_id': 'r1', 'instructor_id': 'i1',
             'course': 'Management Accounting', 'code': 'BUAD301', 'type': 'lecture', 'groups': ['g7'], 'room': 'A3.128', 'instructor': 'Dr. Mohamed Fawzy'}]
VIEW = {'calendar': CAL, 'records': RECORDS, 'sessions': SESSIONS, 'version': 5, 'second_chance': ['k1'], 'exam_run': None,
        'run': {'id': 'run1', 'published': True, 'stale': False, 'sessions': 1}, 'last_status': {'status': 'completed', 'passed': True, 'sessions': 1, 'scope': None}}


def ask(text, previous=None, ar=False):
    meaning = understand(text, VIEW, previous)
    return meaning, answer(meaning, VIEW, ar)


def test_room_busy_and_free_at_a_time_with_follow_up():
    meaning, reply = ask('Is room A3.128 free on Sunday at 9:00?')
    assert meaning['intent'] == 'room_schedule' and reply['text'][0].startswith('No: A3.128 is busy on Sunday 09:00')
    assert 'Management Accounting' in reply['text'][1]
    _, later = ask('and on Monday?', previous=meaning)
    assert later['text'][0] == 'Yes: A3.128 is free on Monday 09:00.'


def test_is_and_it_are_not_programme_initials():
    meaning, _ = ask('is it free on Sunday at 10 in A3.128')
    assert meaning['slots']['programmes'] == []


def test_free_labs_with_seats_at_a_bare_time():
    meaning, reply = ask('free labs on Monday 11:30 for 25 students')
    assert meaning['intent'] == 'free_rooms' and meaning['slots']['window'] == (690, 691)
    assert reply['text'][0] == '1 free rooms on Monday 11:30:' and 'C.101' in reply['text'][1]


def test_group_by_programme_initials_year_and_number_with_free_periods():
    meaning, reply = ask('What does BA Y3 G7 have on Sunday?')
    assert meaning['intent'] == 'group_schedule' and meaning['slots']['groups'] == ['g7']
    assert 'Management Accounting' in reply['text'][1] and reply['text'][2] == 'Free: 10:15–11:45, 12:00–13:30'


def test_instructor_in_arabic():
    meaning, reply = ask('جدول دكتور محمد فوزي يوم الأحد', ar=True)
    assert meaning['intent'] == 'instructor_schedule' and reply['text'][0] == 'Dr. Mohamed Fawzy يوم الأحد:'


def test_generate_is_a_proposed_action_not_done():
    meaning, reply = ask('Generate the timetable for BA year 3')
    assert reply['action'] == {'type': 'generate', 'scope': [{'programme': 'Business Administration', 'year': 3}], 'label': 'Generate', 'version': 5,
                               'filter': {'major': 'Business Administration', 'year': '3'}}
    _, one = ask('i want a schedule for ba year 3 group 7')
    assert one['action']['scope'] == [{'programme': 'Business Administration', 'year': 3, 'group': 'g7'}] and one['action']['filter'] == {'group': 'g7'}
    assert one['text'][0].startswith('I will generate a draft timetable for BA5-G7 only.')
    _, whole = ask('اعمل جدول للجامعة كلها', ar=True)
    assert whole['action']['scope'] is None
    _, vague = ask('generate a timetable')
    assert vague.get('action') is None and 'which programme' in vague['text'][0].lower()


def test_exam_timetable_needs_dates_and_leaves_second_chances_unticked():
    _, ask_dates = ask('create the finals timetable')
    assert ask_dates.get('action') is None and 'dates' in ask_dates['text'][0]
    _, reply = ask('create the finals timetable from 20 Dec to 31 Dec 2026')
    assert reply['action']['body'] == {'kind': 'final', 'start_date': '2026-12-20', 'end_date': '2026-12-31', 'skip': ['k1:makeup']}
    _, quiz = ask('quiz 2 timetable 45 minutes 5-8 jan 2027')
    assert quiz['action']['body'] == {'kind': 'quiz', 'start_date': '2027-01-05', 'end_date': '2027-01-08', 'quiz_number': 2, 'quiz_minutes': 45}


def test_dates():
    today = date(2026, 11, 14)
    assert find_dates('from 2026-12-20 to 2026-12-31', today) == (date(2026, 12, 20), date(2026, 12, 31))
    assert find_dates('20 dec - 3 jan', today) == (date(2026, 12, 20), date(2027, 1, 3))
    assert find_dates('من 20 ديسمبر الى 31 ديسمبر', today) == (date(2026, 12, 20), date(2026, 12, 31))


def test_pdf_link_for_a_group():
    _, reply = ask('download the pdf for BA5-G7')
    assert reply['action']['url'] == '/api/schedules/run1/timetable.pdf?group=g7'


def test_unknown_is_reported():
    meaning, reply = ask('tell me a joke')
    assert meaning['intent'] == 'unknown' and reply.get('unknown')


def test_local_model_fallback_resolves_names_here(monkeypatch):
    monkeypatch.setenv('JADWAI_AI_ENABLED', 'true'); monkeypatch.setenv('JADWAI_AI_PROVIDER', 'local')
    sent = {}

    def handler(req):
        body = json.loads(req.content); sent.update(body)
        content = {'intent': 'room_schedule', 'room': 'A3.128', 'instructor': None, 'group': None, 'programme': None, 'year': None, 'course': None,
                   'days': ['Sunday'], 'start_time': '09:00', 'end_time': None, 'exam_kind': None, 'start_date': None, 'end_date': None, 'whole_university': False}
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(content)}})
    meaning = asyncio.run(model_understand('could you check whether the big hall A3.128 has anything going on sunday morning nine', VIEW, transport=httpx.MockTransport(handler)))
    assert sent['format']['properties']['intent']['enum'][0] == 'room_schedule' and 'Business Administration' in sent['messages'][0]['content']
    assert 'Dr. Mohamed Fawzy' not in json.dumps(sent)  # only the message and programme names go to the model
    assert meaning['slots']['rooms'] == ['r1'] and meaning['slots']['window'] == (540, 541)
    assert answer(meaning, VIEW, False)['text'][0].startswith('No: A3.128 is busy')


def test_local_model_off_or_down(monkeypatch):
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    assert asyncio.run(model_understand('anything', VIEW)) is None
    monkeypatch.setenv('JADWAI_AI_ENABLED', 'true'); monkeypatch.setenv('JADWAI_AI_PROVIDER', 'local')

    def down(_):
        raise httpx.ConnectError('refused')
    assert asyncio.run(model_understand('anything', VIEW, transport=httpx.MockTransport(down))) is None


def test_endpoint_answers_admins_only(environment, monkeypatch):
    from test_workflows import login
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    assert client.post('/api/assistant', json={'text': 'help'}).status_code == 401
    login(client)
    reply = client.post('/api/assistant', json={'text': 'help'}).json()
    assert reply['meaning']['intent'] == 'help' and reply['source'] == 'built-in' and reply['text'][0].startswith('I can answer')
    unknown = client.post('/api/assistant', json={'text': 'tell me a joke'}).json()
    assert unknown['retry_with_model'] is False and unknown['action'] is None  # no local model configured: examples instead
    assert client.get('/api/assistant/configuration').json() == {'model': None, 'local_model': False}
    client.post('/api/auth/logout'); login(client, 'viewer@example.test')
    assert client.post('/api/assistant', json={'text': 'help'}).status_code == 403


def chat(*lines):
    previous, reply = None, None
    for text in lines:
        meaning = understand(text, VIEW, previous)
        reply = answer(meaning, VIEW, bool(ARABIC.search(text)))
        if meaning['intent'] != 'unknown':
            previous = {'intent': meaning['intent'], 'slots': meaning['slots'], **({'asking': True} if reply.get('asking') else {})}
    return reply


def test_unclear_requests_get_a_question_and_typed_or_clicked_answers_complete_them():
    VIEW['records'].append({'id': 'g1', 'kind': 'groups', 'data': {'name': 'Business Administration III G1', 'code': 'BA5-G1', 'major': 'Business Administration', 'year': 3}})
    try:
        first = chat('generate a timetable')
        assert first['asking'] and 'Which programme' in first['text'][0] and {'label': 'Whole university', 'text': 'whole university'} in first['choices']
        assert chat('generate a timetable', 'whole university')['action']['scope'] is None
        groups = chat('i want a schedule for ba year 3')
        assert groups['text'][0] == 'All 2 groups of Business Administration year 3, or one group?' and [c['label'] for c in groups['choices']] == ['All of year 3', 'BA5-G1', 'BA5-G7']
        assert chat('i want a schedule for ba year 3', 'BA5-G7')['action']['scope'][0]['group'] == 'g7'      # clicked
        assert chat('i want a schedule for ba year 3', 'group 7')['action']['scope'][0]['group'] == 'g7'     # typed
        assert chat('i want a schedule for ba year 3', 'all of them')['action']['scope'] == [{'programme': 'Business Administration', 'year': 3}]
        assert chat('اعمل جدول BA سنة 3', 'كلهم')['action']['scope'] == [{'programme': 'Business Administration', 'year': 3}]
        # A new request instead of an answer is treated as a new request.
        assert chat('i want a schedule for ba year 3', 'is room A3.128 free on Sunday at 9:00?')['text'][0].startswith('No: A3.128 is busy')
    finally:
        VIEW['records'].pop()


def test_missing_details_are_asked_for_and_answered():
    assert chat('create the midterm timetable', 'from 20 Dec to 31 Dec 2026')['action']['body'] == {'kind': 'midterm', 'start_date': '2026-12-20', 'end_date': '2026-12-31'}
    assert chat('free rooms please', 'Monday at 11:30')['text'][0] == '3 free rooms on Monday 11:30:'


def test_adding_an_instructor_step_by_step_and_in_one_message():
    reply = chat('create an instructor', 'Sara Ali', 'TA', 'Informatics', 'Thursday')
    assert reply['action']['body'] == {'name': 'Sara Ali', 'code': 'T-SA', 'department': 'Informatics', 'position': 'ta', 'day_off': 'Thursday', 'max_weekly_hours': None}
    one = chat('add Dr. Omar Adel to Informatics, day off Sunday')
    assert one['action']['body']['position'] == 'doctor' and one['action']['body']['day_off'] == 'Sunday' and one['action']['body']['code'] == 'D-OA'
    asks = chat('add a TA named Mariam Samir')
    assert asks['asking'] and asks['text'][-1] == 'Which department is Mariam Samir in?'
    arabic = chat('أضف محاضر جديد', 'سارة علي', 'معيد', 'Informatics', 'لا')
    assert arabic['action']['body']['name'] == 'سارة علي' and arabic['text'][0].startswith('إضافة')  # Arabic all the way through
    assert chat('create an instructor', 'Sara Ali', 'not sure')['text'][0] == "Sorry, I couldn't read that."
    assert chat('create an instructor', 'cancel')['text'][0].startswith('OK, cancelled')


def test_adding_a_room_and_a_group_and_courses_open_their_page():
    room = chat('add room C7.201 with 40 seats', 'lab')
    assert room['action']['body'] == {'name': 'C7.201', 'code': 'C7.201', 'capacity': 40, 'room_types': ['lab']}
    group = chat('add a student group', 'Business Administration', '3', 'G7', '11', '28')  # G7 is taken: asked again
    assert group['action']['body'] == {'name': 'Business Administration Year 3 G11', 'code': 'BA3-G11', 'size': 28, 'year': 3, 'major': 'Business Administration'}
    assert chat('add a new course')['action'] == {'type': 'open', 'page': 'data', 'kind': 'courses', 'label': 'Open Course setup'}
    what = chat('i want to add', 'a room')
    assert what['text'][-1].startswith('What is the room code')


def test_records_built_by_the_chat_pass_the_records_endpoint(environment, monkeypatch):
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    previous = None
    for text in ['add a TA named Laila Hassan', 'Informatics', 'none']:
        reply = client.post('/api/assistant', json={'text': text, 'previous': previous}).json()
        previous = reply['meaning']
    action = reply['action']
    assert action['type'] == 'create_record'
    saved = client.post(f"/api/records/{action['kind']}", json=action['body'], headers=version(client))
    assert saved.status_code == 201, saved.text
    for text, follow in [('add room Z9.100 with 25 seats', 'lab')]:
        r = client.post('/api/assistant', json={'text': text}).json()
        r = client.post('/api/assistant', json={'text': follow, 'previous': r['meaning']}).json()
        assert client.post('/api/records/rooms', json=r['action']['body'], headers=version(client)).status_code == 201
