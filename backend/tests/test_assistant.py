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
SESSIONS = [{'activity_id': 'c1', 'occurrence': 0, 'day': 'Sunday', 'start_minute': 510, 'end_minute': 600, 'room_id': 'r1', 'instructor_id': 'i1',
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
    assert group['action']['body'] == {'name': 'Business Administration III G11', 'code': 'BA3-G11', 'size': 28, 'year': 3, 'major': 'Business Administration'}
    assert chat('add a new course')['text'] == ['What is the course called?']  # courses are created by conversation too
    what = chat('i want to add', 'a room')
    assert what['text'][-1].startswith('What is the room code')


def test_records_built_by_the_chat_pass_the_records_endpoint(environment, monkeypatch):
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    previous = None
    for text in ['add a TA named Laila Hassan', 'Informatics', 'use as new name', 'none']:
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


def test_programme_then_year_then_group_even_with_one_year():
    VIEW['records'].append({'id': 'g9', 'kind': 'groups', 'data': {'name': 'IT Security I G2', 'code': 'ITS1-G2', 'major': 'IT Security', 'year': 1}})
    VIEW['records'].append({'id': 'c9', 'kind': 'courses', 'data': {'name': 'Network Security', 'code': 'SEC101', 'group_ids': ['g8', 'g9']}})
    try:
        year = chat('create schedule', 'IT Security')
        assert year['text'][0] == 'Which year of IT Security? Only year 1 has groups.' and [c['label'] for c in year['choices']] == ['Year 1']
        group = chat('create schedule', 'IT Security', 'year 1')
        assert group['text'][0] == 'All 2 groups of IT Security year 1, or one group?'
        assert [c['label'] for c in group['choices']] == ['All of year 1', 'ITS1-G1', 'ITS1-G2']
        assert chat('create schedule', 'IT Security', 'year 1', 'ITS1-G2')['action']['scope'] == [{'programme': 'IT Security', 'year': 1, 'group': 'g9'}]
        assert chat('create schedule', 'IT Security', '1', 'all of them')['action']['scope'] == [{'programme': 'IT Security', 'year': 1}]
        wrong = chat('create schedule', 'IT Security', '5')
        assert wrong['text'][0] == 'IT Security has no groups in year 5. Which year?' and [c['label'] for c in wrong['choices']] == ['Year 1']
        assert chat('create schedule', 'IT Security', '5', '1')['text'][0].startswith('All 2 groups of IT Security year 1')
        # What the first message already says is not asked again.
        assert chat('create schedule for IT Security year 1')['text'][0].startswith('All 2 groups')
        assert chat('create schedule for ITS1-G2')['action']['scope'][0]['group'] == 'g9'
    finally:
        VIEW['records'].pop(); VIEW['records'].pop()


def test_a_chat_remembers_what_it_talked_about():
    from app.assistant_context import remember, with_context
    from app.assistant import normalise

    def talk(*lines):
        previous, memory, out = None, {}, []
        for text in lines:
            meaning = with_context(normalise(text), understand(text, VIEW, previous), memory)
            reply = answer(meaning, VIEW, bool(ARABIC.search(text)))
            previous = {'intent': meaning['intent'], 'slots': meaning['slots'], **({'asking': True} if reply.get('asking') else {})}
            memory = remember(memory, meaning)
            out.append(reply)
        return out
    room = talk('Is room A3.128 free on Sunday at 9:00?', 'is it free at 11:00?', 'who is in it on Sunday')
    assert room[1]['text'][0] == 'Yes: A3.128 is free on Sunday 11:00.'
    assert room[2]['text'][0] == 'A3.128 on Sunday:'  # a listing question: the whole day
    person = talk("Dr. Mohamed Fawzy's schedule on Monday", 'is he free on Sunday at 9?')
    assert person[1]['text'][0].startswith('No: Dr. Mohamed Fawzy is busy on Sunday 09:00')
    group = talk('What does BA5-G7 have on Sunday?', 'generate a timetable for that group', 'download the pdf for it')
    assert group[1]['action']['scope'][0]['group'] == 'g7' and group[2]['action']['url'].endswith('group=g7')
    arabic = talk('هل قاعة A3.128 فاضية يوم الأحد الساعة 9؟', 'وهي فاضية الساعة 11؟')
    assert arabic[1]['text'][0].startswith('نعم: A3.128')
    # A new chat starts empty: "is it free?" alone has nothing to refer to.
    assert talk('is it free at 11:00?')[0].get('action') is None


def test_chats_are_stored_per_admin_with_their_context(environment, monkeypatch):
    from test_workflows import login
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    first = client.post('/api/assistant', json={'text': 'create an instructor'}).json()
    chat = first['chat_id']
    assert chat and first['meaning']['intent'] == 'create_record'
    second = client.post('/api/assistant', json={'text': 'Sara Ali', 'chat_id': chat}).json()  # context kept on the server
    assert second['text'][-1].startswith('Is Sara Ali a doctor')
    listed = client.get('/api/assistant/chats').json()
    assert listed[0] == {**listed[0], 'id': chat, 'title': 'create an instructor'}
    opened = client.get(f'/api/assistant/chats/{chat}').json()
    assert [m['from'] for m in opened['messages']] == ['you', 'jai', 'you', 'jai'] and opened['messages'][2]['text'] == 'Sara Ali'
    fresh = client.post('/api/assistant/chats').json()
    other = client.post('/api/assistant', json={'text': 'doctor', 'chat_id': fresh['id']}).json()
    assert not any('department' in line for line in other['text'])  # a new chat doesn't continue the other one
    done = client.post(f"/api/assistant/chats/{chat}/messages/{second['message_id']}/done", json={'note': ['Started.']}).json()
    assert done['note']['text'] == ['Started.'] and client.get(f'/api/assistant/chats/{chat}').json()['messages'][3]['done'] is True
    client.post('/api/auth/logout'); login(client, 'viewer@example.test')
    assert client.get(f'/api/assistant/chats/{chat}').status_code == 403
    client.post('/api/auth/logout'); login(client)
    assert client.delete(f'/api/assistant/chats/{chat}').status_code == 204
    assert client.get(f'/api/assistant/chats/{chat}').status_code == 404


def test_pdf_uses_the_timetable_on_screen_and_no_corrects_the_last_request():
    seen = {**VIEW, 'run': {**VIEW['run'], 'id': 'draft9', 'on_screen': True}, 'screen': {'page': 'timetable', 'run_id': 'draft9', 'group': 'g7'}}
    _, pdf = None, answer(understand('save as pdf', seen, None), seen, False)
    assert pdf['action']['url'] == '/api/schedules/draft9/timetable.pdf?group=g7' and pdf['text'][-1] == 'From the timetable on your screen.'
    # "No, this timetable" after a PDF of something named: the one on screen.
    first = understand('download the pdf for Business Administration year 3', seen, None)
    assert answer(first, seen, False)['action']['url'].endswith('year=3&major=Business+Administration')
    corrected = understand('no this timetable', seen, {'intent': first['intent'], 'slots': first['slots']})
    assert corrected['intent'] == 'download_pdf' and answer(corrected, seen, False)['action']['url'].endswith('?group=g7')
    # Corrections keep the request and change what the new words say.
    room = understand('Is room A3.128 free on Sunday at 9:00?', VIEW, None)
    monday = understand('no I meant Monday', VIEW, {'intent': room['intent'], 'slots': room['slots']})
    assert monday['intent'] == 'room_schedule' and monday['slots']['days'] == ['Monday'] and monday['slots']['rooms'] == ['r1']
    assert understand('لا، الساعة 11', VIEW, {'intent': room['intent'], 'slots': room['slots']})['slots']['window'] == (660, 661)
    # A different action after "no" is a new request.
    assert understand('no, generate the timetable for BA year 3', VIEW, {'intent': room['intent'], 'slots': room['slots']})['intent'] == 'generate_timetable'


def test_publishing_explains_what_stands_in_the_way_and_otherwise_asks_to_confirm():
    def ask_publish(text, run, **extra):
        view = {**VIEW, 'run': {**VIEW['run'], **run}, 'published_id': extra.get('published_id'), 'screen': {}, 'published_activities': [] if extra.get('published_id') else None}
        return answer(understand(text, view, None), view, bool(ARABIC.search(text)))
    part = ask_publish('publish it', {'published': False, 'complete': False, 'scope': [{'programme': 'Business Administration', 'year': 3, 'group': 'g7'}]})
    assert part['text'][0].startswith('This draft is only part of the timetable (BA5-G7).') and part.get('action') is None
    assert part['choices'][0]['text'] == 'generate the whole university timetable'
    assert ask_publish('publish it', {'published': False, 'complete': True, 'stale': True})['text'][0].startswith('The data changed')
    assert ask_publish('publish the timetable', {'published': True, 'complete': True})['text'][0] == 'That timetable is already published.'
    ok = ask_publish('انشره', {'published': False, 'complete': True, 'stale': False, 'on_screen': True})
    assert ok['action'] == {'type': 'publish', 'what': 'teaching', 'run_id': 'run1', 'label': 'نشر'}
    # The page is filtered to one group: say what is on screen and that the draft is the whole week.
    view = {**VIEW, 'run': {**VIEW['run'], 'published': False, 'complete': True, 'on_screen': True, 'sessions': 780, 'kept': 448}, 'screen': {'run_id': 'run1', 'group': 'g7'}}
    filtered = answer(understand('publish it', view, None), view, False)
    assert filtered['text'][0] == ("Your screen shows BA5-G7 (1 sessions), but this draft is the whole university's timetable: 780 sessions. "
                                   "332 were planned in this draft and the other 448 keep the times of the timetable it was built on.")
    assert filtered['action']['type'] == 'publish'
    off = ask_publish('unpublish the timetable', {'published': True, 'complete': True}, published_id='run1')
    assert off['action']['type'] == 'unpublish' and off['action']['run_id'] == 'run1'
    one = ask_publish('publish BA5-G7 schedule only', {'published': False, 'complete': True, 'stale': False, 'on_screen': True}, published_id='old')
    assert one['text'][0].startswith("Publish BA5-G7's week (1 sessions)") and one['action']['type'] == 'publish_merged' and one['action']['groups'] == ['g7'], one
    for text in ('show schedule', 'show the draft', 'open the timetable', 'اعرض المسودة'):
        assert understand(text, VIEW, None)['intent'] == 'show_run', text
    assert understand('show the timetable page', VIEW, None)['intent'] == 'open_page'
    # "the published timetable" in a question is not a request to publish.
    assert understand('is room A3.128 free in the published timetable on Sunday at 9?', VIEW, None)['intent'] == 'room_schedule'


def test_website_tasks_are_understood_and_ask_before_changing_anything():
    view = {**VIEW, 'screen': {}, 'rules': [{'id': 'rule1', 'status': 'approved', 'type': 'unavailable', 'instructor_id': 'i1', 'day': 'Sunday', 'start_hour': 8, 'end_hour': 10.5, 'strength': 'mandatory', 'title': 'x'},
                                           {'id': 'rule2', 'status': 'draft', 'type': 'room_unavailable', 'room_id': 'r1', 'day': 'Monday', 'start_hour': 8, 'end_hour': 12, 'strength': 'mandatory', 'title': 'y'}],
            'users': [{'id': 'u1', 'email': 'sara@x.test', 'name': 'Sara Ali', 'role': 'student', 'active': True, 'version': 4}],
            'exams': [{'course_id': 'cat1', 'course_name': 'Management Accounting', 'course_code': 'BUAD301', 'date': '2026-12-21', 'start_time': '11:30', 'end_time': '14:30', 'exam_type': 'final'}]}
    view['records'] = [*VIEW['records'][:-1], {**VIEW['records'][-1], 'data': {**VIEW['records'][-1]['data'], 'course_id': 'cat1'}}]

    def say_to(text, previous=None):
        meaning = understand(text, view, previous)
        return meaning, answer(meaning, view, bool(ARABIC.search(text)))
    m, r = say_to('open the accounts page')
    assert r['action'] == {'type': 'open', 'page': 'accounts', 'label': 'Open Accounts'} and r['auto_open']
    assert say_to('import the rooms from an excel file')[1]['action']['page'] == 'import'
    assert say_to('change the teaching periods')[1]['action']['page'] == 'settings'
    # Constraints: read with the built-in parser, added only after confirming.
    m, r = say_to("Dr. Mohamed Fawzy can't teach on Monday before 10:30")
    assert m['intent'] == 'add_rule' and r['text'][1] == '• Dr. Mohamed Fawzy · unavailable · Monday 08:00–10:30 · required' and r['action']['type'] == 'add_rules'
    assert say_to('show the rules for Dr. Mohamed Fawzy')[1]['text'][1].startswith('• Dr. Mohamed Fawzy · unavailable · Sunday')
    assert say_to('approve the draft rules')[1]['action'] == {'type': 'approve_rules', 'rule_ids': ['rule2'], 'label': 'Approve all'}
    assert say_to('remove the rule for room A3.128')[1]['action'] == {'type': 'delete_rule', 'rule_id': 'rule2', 'label': 'Remove it'}
    # Records: edit and delete.
    edit = say_to('change room A3.128 capacity to 70')[1]['action']
    assert edit['type'] == 'update_record' and edit['body']['capacity'] == 70 and edit['body']['code'] == 'A3.128'
    assert say_to('set Dr. Mohamed Fawzy day off to Thursday')[1]['action']['body']['day_off'] == 'Thursday'
    assert say_to('change BA5-G7 size to 30')[1]['action']['body']['size'] == 30
    gone = say_to('delete room C.102')[1]
    assert gone['action'] == {'type': 'delete_record', 'kind': 'rooms', 'id': 'r3', 'label': 'Delete'} and "can't be undone" in gone['text'][0]
    # Accounts.
    m1, r1 = say_to('create a student account')
    assert r1['text'][0].startswith('Which student group')
    m2, r2 = say_to('BA5-G7', {'intent': m1['intent'], 'slots': m1['slots'], 'asking': True})
    m3, r3 = say_to('Omar Adel', {'intent': m2['intent'], 'slots': m2['slots'], 'asking': True})
    m4, r4 = say_to('omar@x.test', {'intent': m3['intent'], 'slots': m3['slots'], 'asking': True})
    assert r4['action'] == {'type': 'create_account', 'body': {'name': 'Omar Adel', 'email': 'omar@x.test', 'role': 'student', 'group_id': 'g7'}, 'label': 'Create account'}
    assert say_to('reset password for sara@x.test')[1]['action'] == {'type': 'reset_account', 'user_id': 'u1', 'user_version': 4, 'label': 'Make the link'}
    # Sessions: move and lock in the timetable in use.
    move = say_to('move Management Accounting of BA5-G7 from Sunday 8:30 to Monday 10:15')[1]['action']
    assert move == {'type': 'move_session', 'run_id': 'run1', 'change': {'activity_id': 'c1', 'occurrence': 0, 'day': 'Monday', 'start_minute': 615}, 'label': 'Move it'}
    assert say_to('lock Management Accounting of BA5-G7 on Sunday')[1]['action']['type'] == 'lock_session'
    assert say_to('rename this draft to Plan B')[1]['action']['name'] == 'Plan B'
    assert say_to('export csv')[1]['action']['url'] == '/api/schedules/run1/export.csv'
    # Exams.
    assert say_to('when is the Management Accounting final?')[1]['text'][1] == '• Final · Management Accounting · 2026-12-21 11:30–14:30'
    # Questions still answer as before.
    assert say_to('Is room A3.128 free on Sunday at 9:00?')[0]['intent'] == 'room_schedule'


def test_what_the_chat_builds_passes_the_real_endpoints(environment, monkeypatch):
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)

    def ask(text):
        return client.post('/api/assistant', json={'text': text}).json()
    assert client.post('/api/records/rooms', json={'name': 'Q1.100', 'code': 'Q1.100', 'capacity': 40, 'room_types': ['lecture']}, headers=version(client)).status_code == 201
    assert client.post('/api/records/instructors', json={'name': 'Dr. Hala Mostafa', 'code': 'D-HM9', 'department': 'Informatics', 'position': 'doctor'}, headers=version(client)).status_code == 201
    ws = client.get('/api/workspace').json()
    room = next(r for r in ws['records'] if r['kind'] == 'rooms' and r['code'] == 'Q1.100')
    edit = ask(f"change room {room['code']} capacity to 77")['action']
    assert client.put(f"/api/records/rooms/{edit['id']}", json=edit['body'], headers=version(client)).status_code == 200
    assert next(r for r in client.get('/api/workspace').json()['records'] if r['id'] == room['id'])['capacity'] == 77
    teacher = next(r for r in ws['records'] if r['kind'] == 'instructors' and r['code'] == 'D-HM9')
    rule = ask(f"{teacher['name']} can't teach on {ws['calendar']['days'][0]} before 10:00")
    assert rule['action']['type'] == 'add_rules', rule['text']
    saved = client.post('/api/proposals/interpret', json={'text': rule['action']['text'], 'request_key': str(__import__('uuid').uuid4())}, headers=version(client)).json()
    review = client.post(f"/api/proposals/{saved['id']}/review", json={'action': 'create_drafts', 'rationale': 'chat', 'request_key': str(__import__('uuid').uuid4())}, headers=version(client)).json()
    for rid in review['rule_ids']:
        assert client.post(f'/api/rules/{rid}/approve', headers=version(client)).status_code == 200
    assert any(r['status'] == 'approved' for r in client.get('/api/workspace').json()['rules'])
    account = ask('create a viewer account named Lina Fawzy lina@example.test')['action']
    made = client.post('/api/users', json=account['body'])
    assert made.status_code == 201 and made.json()['reset']['token']


def model_says(content):
    def handler(req):
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(content)}})
    return httpx.MockTransport(handler)


BLANK = {'record_kind': None, 'room': None, 'instructor': None, 'group': None, 'programme': None, 'year': None, 'course': None, 'days': [],
         'start_time': None, 'end_time': None, 'exam_kind': None, 'start_date': None, 'end_date': None, 'whole_university': False}


def test_local_model_rewrites_into_any_command_with_one_command_only(monkeypatch):
    monkeypatch.setenv('JADWAI_AI_ENABLED', 'true'); monkeypatch.setenv('JADWAI_AI_PROVIDER', 'local')
    view = {**VIEW, 'screen': {}, 'rules': [], 'users': [], 'exams': []}
    m = asyncio.run(model_understand('A3.128 got renovated and now fits 90 people', view,
                                     transport=model_says({**BLANK, 'command': 'Change room A3.128 capacity to 90', 'intent': 'edit_record'})))
    assert m['intent'] == 'edit_record' and m['rewritten'] == 'Change room A3.128 capacity to 90'
    assert answer(m, view, False)['action']['body']['capacity'] == 90
    # "X and Y": only the part that is the kind of request the model chose.
    m = asyncio.run(model_understand('take Dr. Mohamed Fawzy off the system', view,
                                     transport=model_says({**BLANK, 'command': 'Unpublish the timetable and delete instructor Dr. Mohamed Fawzy', 'intent': 'delete_record'})))
    assert m['intent'] == 'delete_record' and m['rewritten'] == 'delete instructor Dr. Mohamed Fawzy'
    m = asyncio.run(model_understand('take Dr. Mohamed Fawzy off the system', view,
                                     transport=model_says({**BLANK, 'command': 'Unpublish the timetable and delete instructor Dr. Mohamed Fawzy', 'intent': 'unknown'})))
    assert m is None or m.get('rewritten') != 'Unpublish the timetable and delete instructor Dr. Mohamed Fawzy'


def test_a_reading_from_a_name_alone_is_marked_unsure():
    assert understand('A3.128 got renovated and now fits 90 people', VIEW, None).get('weak')
    assert not understand('Is room A3.128 free on Sunday at 9?', VIEW, None).get('weak')
    assert not understand('A3.128 on Sunday', VIEW, None).get('weak')


def test_plural_days_and_more_edit_wordings():
    assert understand('Is room A3.128 free on Sundays at 9?', VIEW, None)['slots']['days'] == ['Sunday']
    edit = understand('could you bump the number of seats in A3.128 up to 70', VIEW, None)
    assert edit['intent'] == 'edit_record'


def test_moves_narrow_by_context_offer_sessions_and_free_times():
    sessions = [*SESSIONS, {'activity_id': 'c1', 'occurrence': 1, 'day': 'Monday', 'start_minute': 615, 'end_minute': 705, 'room_id': 'r1', 'instructor_id': 'i1',
                            'course': 'Management Accounting', 'code': 'BUAD301', 'type': 'lecture', 'groups': ['g7'], 'room': 'A3.128', 'instructor': 'Dr. Mohamed Fawzy'}]
    view = {**VIEW, 'sessions': sessions, 'screen': {}, 'memory': {}}
    many = answer(understand('move Management Accounting', view, None), view, False)
    assert many['text'][0] == '2 sessions match. Which one?' and [c['text'] for c in many['choices']] == ['BUAD301 on Sunday 08:30', 'BUAD301 on Monday 10:15']
    # The day the chat was talking about picks one; then free times are offered.
    view['memory'] = {'days': ['Monday']}
    where = answer(understand('move Management Accounting', view, None), view, False)
    assert where['text'][0].startswith('Where should Management Accounting (BUAD301, Monday 10:15) go?')
    assert {'label': 'Saturday 08:30', 'text': 'to Saturday 08:30'} in where['choices']
    assert {'label': 'Sunday 08:30', 'text': 'to Sunday 08:30'} not in where['choices']  # the group is busy then
    first = understand('move Management Accounting', view, None)
    done = understand('to Saturday 08:30', view, {'intent': first['intent'], 'slots': first['slots'], 'asking': True})
    assert answer(done, view, False)['action']['change'] == {'activity_id': 'c1', 'occurrence': 1, 'day': 'Saturday', 'start_minute': 510}


def test_parts_are_planned_inside_and_published_into_the_published_timetable():
    view = {**VIEW, 'screen': {}, 'published_id': 'pub1'}
    gen = answer(understand('i want a schedule for ba year 3 group 7', view, None), view, False)
    assert gen['action']['base_run_id'] == 'pub1' and gen['action']['replace'] is True
    assert 'planned inside the published timetable' in gen['text'][0]
    whole = answer(understand('generate the whole university timetable', view, None), view, False)
    assert 'base_run_id' not in whole['action']
    part = {**view, 'run': {**VIEW['run'], 'published': False, 'complete': False, 'stale': False, 'scope': [{'programme': 'Business Administration', 'year': 3, 'group': 'g7'}]}}
    pub = answer(understand('publish it', part, None), part, False)
    assert pub['action'] == {'type': 'publish_merged', 'run_id': 'run1', 'label': 'Publish into the published timetable', 'again': 'generate a timetable for BA5-G7'}
    assert 'checked for room, instructor and student clashes' in pub['text'][0]


def test_pointing_back_means_the_record_the_chat_is_about():
    from app.assistant_context import remember_record, resolve_references
    group = remember_record({}, 'groups', 'g7')
    assert resolve_references('create a schedule for them', group, VIEW)[0] == 'create a schedule for BA5-G7'
    assert resolve_references('how many students are in the group I just created?', group, VIEW)[0] == 'how many students are in BA5-G7?'
    assert resolve_references('اعمل جدول للمجموعة الجديدة', group, VIEW)[0] == 'اعمل جدول للمجموعة BA5-G7'
    assert resolve_references('change its size to 32', group, VIEW)[0] == "change BA5-G7's size to 32"
    assert resolve_references('publish it', group, VIEW)[0] == 'publish it'  # "it" is the timetable there
    assert resolve_references('create a schedule for them', {}, VIEW)[0] == 'create a schedule for them'  # a new chat has nothing to point at
    view = {**VIEW, 'screen': {}, 'memory': group}
    info = answer(understand(resolve_references("what's its size?", group, view)[0], view, None), view, False)
    assert info['text'][0] == 'BA5-G7: 0 students · Business Administration year 3 · in 1 course activities' or info['text'][0].startswith('BA5-G7:')
    room = remember_record({}, 'rooms', 'r1')
    assert answer(understand('lock it', {**view, 'memory': room}, None), {**view, 'memory': room}, False)['text'][0].startswith('Only a session can be locked')


def test_a_group_in_no_course_has_nothing_to_schedule():
    records = [*VIEW['records'], {'id': 'g9', 'kind': 'groups', 'data': {'name': 'IT Security III G4', 'code': 'IS3-G4', 'major': 'IT Security', 'year': 3, 'size': 30}}]
    view = {**VIEW, 'records': records, 'screen': {}}
    reply = answer(understand('create a schedule for IS3-G4', view, None), view, False)
    assert reply['text'][0].startswith('IS3-G4 is not in any course yet') and reply['action']['page'] == 'courses'


def test_a_created_record_becomes_what_the_chat_is_about(environment, monkeypatch):
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    group = client.post('/api/records/groups', json={'name': 'Data Science Year 3 G9', 'code': 'DS3-G9', 'size': 25, 'year': 3, 'major': 'Data Science'}, headers=version(client)).json()
    first = client.post('/api/assistant', json={'text': 'add a student group'}).json()
    chat = first['chat_id']
    assert client.post(f"/api/assistant/chats/{chat}/messages/{first['message_id']}/done", json={'note': ['Added.'], 'subject_kind': 'groups', 'subject_id': group['id']}).status_code == 200
    reply = client.post('/api/assistant', json={'text': 'create a schedule for them', 'chat_id': chat}).json()
    assert reply['text'][0].startswith('DS3-G9 is not in any course yet')


def test_creating_a_course_step_by_step(environment, monkeypatch):
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    add = lambda kind, body: client.post(f'/api/records/{kind}', json=body, headers=version(client)).json()['id']
    g1 = add('groups', {'name': 'IT Security Year 3 G4', 'code': 'IS3-G4', 'size': 30, 'year': 3, 'major': 'IT Security'})
    g2 = add('groups', {'name': 'IT Security Year 3 G5', 'code': 'IS3-G5', 'size': 28, 'year': 3, 'major': 'IT Security'})
    doctor = add('instructors', {'name': 'Dr. Hala Mostafa', 'code': 'D-HM9', 'department': 'Informatics', 'position': 'doctor'})
    ta = add('instructors', {'name': 'Omar Lotfy', 'code': 'T-OL9', 'department': 'Informatics', 'position': 'ta'})
    chat, reply = None, None
    for text in ['create a new course', 'Network Security', 'SEC301', 'IS3-G4', 'lecture and lab', 'Hala Mostafa', 'Omar Lotfy']:
        reply = client.post('/api/assistant', json={'text': text, **({'chat_id': chat} if chat else {})}).json()
        chat = reply['chat_id']
    action = reply['action']
    assert action['type'] == 'create_course', reply['text']
    assert action['catalog'] == {'name': 'Network Security', 'code': 'SEC301', 'eligibility': {'lecture': [doctor], 'tutorial': [], 'lab': [ta]},
                                 'group_ids': [g1], 'quiz_count': 3, 'second_chance': True}
    assert [(a['code'], a['activity_type']) for a in action['activities']] == [('SEC301-L', 'lecture'), ('SEC301-LAB-G4', 'lab')]
    # Saved the way the chat window saves it: catalogue course, then its sessions.
    course = client.post('/api/course-catalog', json=action['catalog'], headers=version(client))
    assert course.status_code == 201, course.text
    for a in action['activities']:
        assert client.post('/api/records/courses', json={**a, 'course_id': course.json()['id']}, headers=version(client)).status_code == 201
    # Then another group joins it: the shared lecture grows and the group gets its own lab.
    more = client.post('/api/assistant', json={'text': 'add IS3-G5 to Network Security'}).json()['action']
    assert more['type'] == 'update_course' and more['catalog']['group_ids'] == [g1, g2] and [c['code'] for c in more['creates']] == ['SEC301-LAB-G5']
    assert client.put(f"/api/course-catalog/{more['course_id']}", json=more['catalog'], headers=version(client)).status_code == 200
    for u in more['updates']:
        assert client.put(f"/api/records/courses/{u['id']}", json=u['body'], headers=version(client)).status_code == 200
    for c in more['creates']:
        assert client.post('/api/records/courses', json=c, headers=version(client)).status_code == 201
    acts = [r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'courses' and r['code'].startswith('SEC301')]
    assert sorted((r['code'], tuple(r['group_ids'])) for r in acts) == [('SEC301-L', (g1, g2)), ('SEC301-LAB-G4', (g1,)), ('SEC301-LAB-G5', (g2,))]
    # A TA can't be named for lectures.
    assert 'doctors teach lectures' in client.post('/api/assistant', json={'text': 'add Omar Lotfy to Network Security lectures'}).json()['text'][0]


def test_programmes_by_part_of_their_name_and_a_year_question():
    from app.assistant import find_programme
    records = [*VIEW['records'],
               {'id': 'a1', 'kind': 'groups', 'data': {'name': 'ACSI II G1', 'code': 'INF2-G1', 'major': 'Applied Computer Science & Informatics', 'year': 2}},
               {'id': 'a2', 'kind': 'groups', 'data': {'name': 'ACSI I G1', 'code': 'INF1-G1', 'major': 'Applied Computer Science & Informatics', 'year': 1}},
               {'id': 'b1', 'kind': 'groups', 'data': {'name': 'BI II G1', 'code': 'BI3-G1', 'major': 'Business Informatics', 'year': 2}}]
    assert find_programme('computer science year 2', records) == ['Applied Computer Science & Informatics']
    assert find_programme('security', records) == ['IT Security']
    assert find_programme('is room a3 free', records) == []
    view = {**VIEW, 'records': records, 'screen': {}, 'memory': {}, 'catalog': []}

    def talk(*lines):
        previous, reply = None, None
        for text in lines:
            meaning = understand(text, view, previous)
            reply = answer(meaning, view, False)
            previous = {'intent': meaning['intent'], 'slots': meaning['slots'], **({'asking': True} if reply.get('asking') else {})}
        return reply, previous
    reply, state = talk('create a new course', 'Intro SE', 'ISE303', 'Computer Science Year 2')
    assert reply['text'][0].startswith('What teaching') and state['slots']['form']['groups'] == ['a1']
    reply, _ = talk('create a new course', 'Intro SE', 'ISE303', 'Applied Computer Science & Informatics')
    assert reply['text'][0] == 'Which year of Applied Computer Science & Informatics?' and [c['label'] for c in reply['choices']] == ['Year 1', 'Year 2', 'All years']
    _, state = talk('create a new course', 'Intro SE', 'ISE303', 'Applied Computer Science & Informatics', 'Year 2')
    assert state['slots']['form']['groups'] == ['a1']
    reply, _ = talk('create a new course', 'Intro SE', 'ISE303', 'Informatics')
    assert reply['text'][0] == 'Which programme do you mean?' and {c['label'] for c in reply['choices']} == {'Applied Computer Science & Informatics', 'Business Informatics'}


def test_big_lectures_split_into_sections_that_fit_a_hall():
    from app.assistant_courses import lecture_sections
    records = [{'id': 'hall', 'kind': 'rooms', 'data': {'code': 'H1', 'capacity': 100, 'room_types': ['lecture']}}] + \
              [{'id': f'x{n}', 'kind': 'groups', 'data': {'code': f'CS2-G{n}', 'major': 'CS', 'year': 2, 'size': 30}} for n in range(1, 8)]
    view = {'records': records}
    sections = lecture_sections([f'x{n}' for n in range(7, 0, -1)], view)
    assert [len(s) for s in sections] == [3, 3, 1] or [len(s) for s in sections] == [3, 2, 2]
    assert all(sum(30 for _ in s) <= 100 for s in sections) and sections[0][0] == 'x1'  # in group order


def test_a_new_group_is_offered_its_cohorts_courses(environment, monkeypatch):
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    add = lambda kind, body: client.post(f'/api/records/{kind}', json=body, headers=version(client)).json()['id']
    hall = add('rooms', {'name': 'H9', 'code': 'H9', 'capacity': 200, 'room_types': ['lecture']})
    g1 = add('groups', {'name': 'CS Year 2 G1', 'code': 'CS2-G1', 'size': 30, 'year': 2, 'major': 'Computer Science'})
    doctor = add('instructors', {'name': 'Dr. Hala Mostafa', 'code': 'D-HM9', 'department': 'Informatics', 'position': 'doctor'})
    ta = add('instructors', {'name': 'Omar Lotfy', 'code': 'T-OL9', 'department': 'Informatics', 'position': 'ta'})
    course = client.post('/api/course-catalog', json={'name': 'Algorithms', 'code': 'ALG201', 'eligibility': {'lecture': [doctor], 'tutorial': [ta], 'lab': []}, 'group_ids': [g1]}, headers=version(client)).json()['id']
    for body in [{'code': 'ALG201-L', 'activity_type': 'lecture', 'eligible_instructors': [doctor], 'group_ids': [g1]},
                 {'code': 'ALG201-G1', 'activity_type': 'tutorial', 'eligible_instructors': [ta], 'group_ids': [g1]}]:
        assert client.post('/api/records/courses', json={**body, 'name': 'Algorithms', 'sessions': 1, 'duration': 90, 'course_id': course}, headers=version(client)).status_code == 201
    g2 = add('groups', {'name': 'CS Year 2 G2', 'code': 'CS2-G2', 'size': 30, 'year': 2, 'major': 'Computer Science'})
    reply = client.post('/api/assistant', json={'text': 'create a schedule for CS2-G2'}).json()
    assert reply['text'][1] == 'The other Computer Science year 2 groups take 1 courses: Algorithms (ALG201).'
    action = reply['action']
    assert action['type'] == 'update_courses' and action['items'][0]['catalog']['group_ids'] == [g1, g2]
    item = action['items'][0]
    assert client.put(f"/api/course-catalog/{item['course_id']}", json=item['catalog'], headers=version(client)).status_code == 200
    for u in item['updates']:
        assert client.put(f"/api/records/courses/{u['id']}", json=u['body'], headers=version(client)).status_code == 200
    for c in item['creates']:
        assert client.post('/api/records/courses', json=c, headers=version(client)).status_code == 201
    acts = {r['code']: r['group_ids'] for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'courses'}
    assert acts == {'ALG201-L': [g1, g2], 'ALG201-G1': [g1], 'ALG201-G2': [g2]}
    assert hall


def test_problems_are_found_before_generating_and_fixed(environment, monkeypatch):
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    add = lambda kind, body: client.post(f'/api/records/{kind}', json=body, headers=version(client)).json()['id']
    add('rooms', {'name': 'Hall', 'code': 'HALL1', 'capacity': 60, 'room_types': ['lecture']})
    add('rooms', {'name': 'Lab', 'code': 'LAB1', 'capacity': 30, 'room_types': ['lab']})
    groups = [add('groups', {'name': f'CS Year 2 G{n}', 'code': f'CS2-G{n}', 'size': 25 if n < 4 else 35, 'year': 2, 'major': 'Computer Science'}) for n in range(1, 5)]
    doctor = add('instructors', {'name': 'Dr. Hala Mostafa', 'code': 'D-HM9', 'department': 'Informatics', 'position': 'doctor'})
    ta = add('instructors', {'name': 'Omar Lotfy', 'code': 'T-OL9', 'department': 'Informatics', 'position': 'ta'})
    course = client.post('/api/course-catalog', json={'name': 'Algorithms', 'code': 'ALG201', 'eligibility': {'lecture': [doctor], 'tutorial': [], 'lab': [ta]}, 'group_ids': groups}, headers=version(client)).json()['id']
    sessions = [{'code': 'ALG201-L', 'activity_type': 'lecture', 'eligible_instructors': [doctor], 'group_ids': groups}] + \
               [{'code': f'ALG201-LAB-G{n}', 'activity_type': 'lab', 'eligible_instructors': [ta], 'group_ids': [g]} for n, g in enumerate(groups, 1)]
    for body in sessions:
        assert client.post('/api/records/courses', json={**body, 'name': 'Algorithms', 'sessions': 1, 'duration': 90, 'course_id': course}, headers=version(client)).status_code == 201
    assert not client.get('/api/schedules/preflight/current').json()['ready']
    reply = client.post('/api/assistant', json={'text': 'generate the timetable for computer science year 2', 'chat_id': None}).json()
    if reply.get('choices'):  # "all groups or one?"
        reply = client.post('/api/assistant', json={'text': 'all of them', 'chat_id': reply['chat_id']}).json()
    assert reply['text'][0].startswith('Before generating'), reply['text']
    assert any('ALG201-L puts 110 students in one lecture; the largest lecture hall seats 60' in line for line in reply['text'])
    assert any('CS2-G4 has 35 students' in line for line in reply['text'])
    action = reply['action']
    assert action['type'] == 'apply_changes' and action['then']['type'] == 'generate' and action['label'] == 'Fix and generate'
    for step in action['steps']:
        method = client.put if step['method'] == 'PUT' else client.post
        assert method(f"/api/{step['path'].lstrip('/')}", json=step['body'], headers=version(client)).status_code in (200, 201)
    checks = client.get('/api/schedules/preflight/current').json()
    assert checks['ready'], checks['blockers']
    codes = sorted(r['code'] for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'courses' and r['activity_type'] == 'lecture')
    assert codes == ['ALG201-L-I', 'ALG201-L-II']
    assert client.post('/api/assistant', json={'text': 'fix the problems'}).json()['text'][0] == 'Nothing blocks generation right now.'


def test_a_group_too_big_for_its_labs_is_split_in_two(environment, monkeypatch):
    import json as _json
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    add = lambda kind, body: client.post(f'/api/records/{kind}', json=body, headers=version(client)).json()['id']
    add('rooms', {'name': 'Hall', 'code': 'HALL1', 'capacity': 200, 'room_types': ['lecture']})
    add('rooms', {'name': 'Lab', 'code': 'LAB1', 'capacity': 30, 'room_types': ['lab']})
    g1 = add('groups', {'name': 'CS Year 2 G1', 'code': 'CS2-G1', 'size': 25, 'year': 2, 'major': 'Computer Science'})
    big = add('groups', {'name': 'CS Year 2 G2', 'code': 'CS2-G2', 'size': 35, 'year': 2, 'major': 'Computer Science'})
    doctor = add('instructors', {'name': 'Dr. Hala Mostafa', 'code': 'D-HM9', 'department': 'Informatics', 'position': 'doctor'})
    ta = add('instructors', {'name': 'Omar Lotfy', 'code': 'T-OL9', 'department': 'Informatics', 'position': 'ta'})
    course = client.post('/api/course-catalog', json={'name': 'Algorithms', 'code': 'ALG201', 'eligibility': {'lecture': [doctor], 'tutorial': [], 'lab': [ta]}, 'group_ids': [g1, big]}, headers=version(client)).json()['id']
    for body in [{'code': 'ALG201-L', 'activity_type': 'lecture', 'eligible_instructors': [doctor], 'group_ids': [g1, big]},
                 {'code': 'ALG201-LAB-G1', 'activity_type': 'lab', 'eligible_instructors': [ta], 'group_ids': [g1]},
                 {'code': 'ALG201-LAB-G2', 'activity_type': 'lab', 'eligible_instructors': [ta], 'group_ids': [big]}]:
        assert client.post('/api/records/courses', json={**body, 'name': 'Algorithms', 'sessions': 1, 'duration': 90, 'course_id': course}, headers=version(client)).status_code == 201
    found = client.post('/api/assistant', json={'text': 'fix the problems'}).json()
    assert {'label': 'Split CS2-G2 into two groups', 'text': 'split CS2-G2 into two groups'} in found['choices']
    reply = client.post('/api/assistant', json={'text': 'split CS2-G2 into two groups'}).json()
    assert reply['text'][0] == 'Split CS2-G2 (35 students) into CS2-G2 (18) and a new CS2-G3 (17)?'
    made = {}
    for step in reply['action']['steps']:  # as the chat window runs them, "$new" becoming the new group's id
        path = step['path'].replace('$new', made.get('new', '$new'))
        body = _json.loads(_json.dumps(step['body']).replace('$new', made.get('new', '$new')))
        res = (client.put if step['method'] == 'PUT' else client.post)(f'/api{path}', json=body, headers=version(client))
        assert res.status_code in (200, 201), (step['path'], res.text)
        if step.get('save_as'):
            made[step['save_as']] = res.json()['id']
    records = client.get('/api/workspace').json()['records']
    sizes = {r['code']: r['size'] for r in records if r['kind'] == 'groups'}
    assert sizes == {'CS2-G1': 25, 'CS2-G2': 18, 'CS2-G3': 17}
    acts = {r['code']: r['group_ids'] for r in records if r['kind'] == 'courses'}
    assert acts['ALG201-L'] == [g1, big, made['new']] and acts['ALG201-LAB-G3'] == [made['new']]
    assert client.get('/api/schedules/preflight/current').json()['ready']


def test_moving_by_day_and_period_in_the_group_on_screen():
    view = {**VIEW, 'screen': {'page': 'timetable', 'group': 'g7'}, 'memory': {}}
    move = answer(understand('move first slot on sunday to third on monday', view, None), view, False)
    assert move['action']['change'] == {'activity_id': 'c1', 'occurrence': 0, 'day': 'Monday', 'start_minute': 720}
    empty = answer(understand('move first slot on monday to third on sunday', view, None), view, False)
    assert empty['text'][0].startswith('There is no session there')
    # A command is never taken as "the same as before, on another day".
    previous = understand('download the pdf for BA5-G7', view, None)
    assert understand('move first slot on sunday to third on monday', view, {'intent': previous['intent'], 'slots': previous['slots']})['intent'] == 'move_session'


def test_a_better_timetable_is_proposed_applied_and_regenerated(environment, monkeypatch):
    import json as _json
    from test_workflows import login, version
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, _ = environment
    login(client)
    reply = client.post('/api/assistant', json={'text': 'a better timetable please'}).json()
    assert reply['text'][0] == 'What would make it better?' and 'Two free days' in [c['label'] for c in reply['choices']]
    group = client.post('/api/records/groups', json={'name': 'CS Year 2 G1', 'code': 'CS2-G1', 'size': 25, 'year': 2, 'major': 'Computer Science'}, headers=version(client)).json()['id']
    reply = client.post('/api/assistant', json={'text': 'give CS2-G1 two free days and no classes before 10'}).json()
    action = reply['action']
    assert action['type'] == 'apply_changes' and action['then']['type'] == 'generate', reply['text']
    made = {}
    for step in action['steps']:  # as the chat window runs them
        path = step['path']
        for key, ident in made.items():
            path = path.replace(f'${key}', ident)
        res = client.post(f'/api{path}', json=step['body'], headers=version(client))
        assert res.status_code in (200, 201), (path, res.text)
        if step.get('save_as'):
            made[step['save_as']] = res.json()['id']
    rules = [r for r in client.get('/api/workspace').json()['rules'] if r['group_id'] == group]
    assert len(rules) == 3 and all(r['status'] == 'approved' for r in rules)
    assert sorted((r['day'], r['start_hour'], r['end_hour']) for r in rules if r['day']) == [('Saturday', 8, 18), ('Thursday', 8, 18)] or len([r for r in rules if r['day']]) == 2
    assert any(r['day'] is None and r['end_hour'] == 10 for r in rules)


def test_a_clashing_move_names_the_clash_and_offers_moves_that_work(environment, monkeypatch):
    from uuid import uuid4
    from test_workflows import login, version
    from app.schedule_worker import process_one
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    client, factory = environment
    login(client)
    add = lambda kind, body: client.post(f'/api/records/{kind}', json=body, headers=version(client)).json()['id']
    add('rooms', {'name': 'Hall', 'code': 'HALL1', 'capacity': 80, 'room_types': ['lecture']})
    add('rooms', {'name': 'Hall 2', 'code': 'HALL2', 'capacity': 80, 'room_types': ['lecture']})
    g1 = add('groups', {'name': 'CS Year 2 G1', 'code': 'CS2-G1', 'size': 25, 'year': 2, 'major': 'Computer Science'})
    g2 = add('groups', {'name': 'CS Year 2 G2', 'code': 'CS2-G2', 'size': 25, 'year': 2, 'major': 'Computer Science'})
    doctor = add('instructors', {'name': 'Dr. Hala Mostafa', 'code': 'D-HM9', 'department': 'Informatics', 'position': 'doctor'})
    for code, groups in (('ALG201-L', [g1]), ('NET202-L', [g2])):
        assert client.post('/api/records/courses', json={'name': code[:6], 'code': code, 'activity_type': 'lecture', 'sessions': 1, 'duration': 90,
                                                          'eligible_instructors': [doctor], 'group_ids': groups}, headers=version(client)).status_code == 201
    from app.models import WorkerHeartbeat, utcnow
    with factory.begin() as db:
        db.add(WorkerHeartbeat(id=1, seen_at=utcnow()))  # the worker looks alive, as in the generation tests
    run = client.post('/api/schedules', json={'request_key': str(uuid4())}, headers=version(client)).json()
    assert process_one(factory), run
    run = client.get(f"/api/schedules/{run['id']}").json()
    assert run['status'] == 'completed', run['result']
    rows = {a['activity_id']: a for a in run['result']['assignments']}
    acts = {r['code']: r['id'] for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'courses'}
    other = rows[acts['NET202-L']]  # the same doctor teaches it: moving ALG201-L onto it clashes
    hhmm = f"{other['start_minute'] // 60:02d}:{other['start_minute'] % 60:02d}"
    screen = {'page': 'timetable', 'run_id': run['id'], 'group': g1}
    reply = client.post('/api/assistant', json={'text': f"move ALG201-L to {other['day']} {hhmm}", 'screen': screen}).json()
    assert reply['text'][0].startswith(f"ALG201 (ALG201-L) can't move to {other['day']} {hhmm}:"), reply['text']
    assert any('instructor Dr. Hala Mostafa already has NET202-L' in line for line in reply['text'])
    assert reply['choices'] and reply['action'] is None
    pick = client.post('/api/assistant', json={'text': reply['choices'][0]['text'], 'chat_id': reply['chat_id'], 'screen': screen}).json()
    move = pick['action']
    assert move['type'] == 'move_session', pick['text']
    done = client.post(f"/api/schedules/{move['run_id']}/edits", json={'request_key': str(uuid4()), 'changes': [move['change']]}, headers=version(client))
    assert done.status_code == 201, done.text  # what JAI suggests, the server accepts
    again = client.post('/api/assistant', json={'text': 'what are the other options', 'chat_id': reply['chat_id'], 'screen': screen}).json()
    assert again['text'][0].startswith('Where should ALG201') and again['choices']


def test_first_slot_means_the_first_class_when_that_period_is_empty():
    later = {**SESSIONS[0], 'start_minute': 720, 'end_minute': 810}  # BA5-G7's only Sunday class is in period 3
    view = {**VIEW, 'sessions': [later], 'screen': {'page': 'timetable', 'group': 'g7'}, 'memory': {}}
    reply = answer(understand('move first slot on sunday to second on monday', view, None), view, False)
    assert reply['text'][0] == 'That period is empty, so I took the first class of the day: Management Accounting at 12:00.'
    assert reply['action']['change'] == {'activity_id': 'c1', 'occurrence': 0, 'day': 'Monday', 'start_minute': 615}
    assert answer(understand('move first slot on monday to second on sunday', view, None), view, False)['text'][0].startswith('There is no session there')


def test_why_a_shared_lecture_cannot_move_is_explained():
    session = {**SESSIONS[0], 'groups': ['g7', 'g8']}
    view = {**VIEW, 'sessions': [session], 'screen': {'page': 'timetable', 'group': 'g7'}, 'memory': {}, 'run_rows': None}
    first = understand('move first slot on sunday to second on monday', view, None)
    why = understand('why is this a problem, these are other groups', view, {'intent': first['intent'], 'slots': first['slots'], 'asking': True})
    assert why['intent'] == 'move_session' and why['slots'].get('explain')


def test_programme_structure_questions():
    records = [*VIEW['records'], {'id': 'g5', 'kind': 'groups', 'data': {'name': 'BA III G5', 'code': 'BA5-G5', 'major': 'Business Administration', 'year': 3, 'size': 30}},
               {'id': 'g6', 'kind': 'groups', 'data': {'name': 'BA II G1', 'code': 'BA3-G1', 'major': 'Business Administration', 'year': 2, 'size': 20}}]
    view = {**VIEW, 'records': records, 'screen': {}, 'memory': {}}
    years = answer(understand('show study year for ba', view, None), view, False)
    assert years['text'] == ['Business Administration has 2 study years:', '• Year 2: 1 groups, 20 students', '• Year 3: 2 groups, 30 students']
    assert [c['label'] for c in years['choices']] == ['Groups in year 2', 'Groups in year 3']
    groups = answer(understand('which groups are in Business Administration year 3', view, None), view, False)
    assert groups['text'] == ['Business Administration year 3: 2 groups: BA5-G5, BA5-G7']
    assert answer(understand('list programmes', view, None), view, False)['text'][0] == '2 programmes:'



def test_here_means_the_programme_and_year_just_talked_about():
    from app.assistant_context import remember
    view = {**VIEW, 'screen': {}, 'memory': {}}
    first = understand('which groups are in Business Administration year 3', view, None)
    memory = remember({}, first)
    view['memory'] = memory
    here = understand('create a new study group here', view, None)
    assert here['intent'] == 'create_record' and here['slots']['form'] == {'major': 'Business Administration', 'year': 3}
    reply = answer(here, view, False)
    assert reply['text'][-1].startswith('Which group number?')
    assert understand('create a new study group', view, None)['slots']['form'] == {}  # without "here", JAI asks as before


def test_a_whole_university_too_big_for_one_run_is_planned_in_parts(monkeypatch):
    import app.solver
    from app.assistant import plan_parts
    monkeypatch.setattr(app.solver, 'MAX_SESSIONS', 5)
    records = [*VIEW['records']]
    for n, (major, year) in enumerate([('Business Administration', 3)] * 4 + [('IT Security', 1)] * 3):
        group = 'g7' if major == 'Business Administration' else 'g8'
        records.append({'id': f'a{n}', 'kind': 'courses', 'data': {'name': f'C{n}', 'code': f'C{n}', 'sessions': 1, 'group_ids': [group]}})
    view = {**VIEW, 'records': records}
    parts = plan_parts(view, limit=5)
    assert parts == [[{'programme': 'Business Administration', 'year': None}], [{'programme': 'IT Security', 'year': None}]]
    assert plan_parts({**VIEW}, limit=5) is None  # small enough for one run
