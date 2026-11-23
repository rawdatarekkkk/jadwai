import asyncio
import json
import httpx
import pytest
from app.main import app
from app.assistant_capabilities import catalogue, contract, validate_action, converse
from test_assistant import VIEW


def test_catalogue_tracks_website_and_excludes_credentials():
    routes = catalogue(app)
    for route in ('PUT /api/workspace', 'GET /api/evaluation', 'GET /api/proposals', 'POST /api/advising-students', 'PUT /api/users/{ident}'):
        assert route in routes
    assert not any('/auth' in k or '/assistant' in k for k in routes)
    for route in routes.values():
        assert contract(route)  # every exposed action has a usable runtime contract


def test_action_validation_rejects_invented_routes_missing_fields_and_path_escape():
    for operation, args in [
        ('POST https://attacker.test', {}), ('POST /api/auth/login', {}),
        ('POST /api/records/{kind}', {'path': {'kind': 'rooms'}, 'body': {}}),
        ('DELETE /api/records/{kind}/{ident}', {'path': {'kind': 'rooms', 'ident': '../users'}}),
        ('GET /api/workspace', {'query': {'invented': 'x'}}),
    ]:
        with pytest.raises(ValueError):
            validate_action(app, operation, args)


def test_model_can_discuss_tradeoffs_and_remembers_conversation_without_actions():
    sent = []
    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps({'operation': '', 'reply': 'Two free days leave four teaching days. Which group should we consider?'})}})
    history = [{'role': 'user', 'content': 'I want two free days for my students.'}]
    reply = asyncio.run(converse('How should I compare timetable quality?', VIEW, history, ('local', 'http://127.0.0.1:11434', 5), app, transport=httpx.MockTransport(handler)))
    assert 'four teaching days' in reply['text'][0] and not reply.get('action')
    assert history[0] in sent[0]['messages']
    assert not any('Authorization' in m for m in sent)


def test_model_missing_details_are_followup_questions_not_guessed_writes():
    replies = [{'operation': 'PUT /api/workspace', 'reply': 'We can change semester settings.'},
               {'reply': 'What should the semester be called?', 'ready': False, 'arguments': '{}'}]
    def handler(req):
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(replies.pop(0))}})
    reply = asyncio.run(converse('Change semester settings', VIEW, [], ('local', 'http://127.0.0.1:11434', 5), app, transport=httpx.MockTransport(handler)))
    assert reply['asking'] and reply['pending']['operation'] == 'PUT /api/workspace' and not reply.get('action')


def test_model_proposal_uses_real_contract_and_does_not_execute():
    replies = [{'operation': 'PUT /api/records/{kind}/{ident}', 'reply': 'I can update the room.'},
               {'reply': 'Change A3.128 to 90 seats?', 'ready': True,
                'arguments': json.dumps({'path': {'kind': 'rooms', 'ident': 'r1'}, 'body': {'name': 'A3.128', 'code': 'A3.128', 'capacity': 90, 'room_types': ['lecture']}})}]
    def handler(req):
        assert str(req.url) == 'http://127.0.0.1:11434/api/chat'
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(replies.pop(0))}})
    reply = asyncio.run(converse('The hall now fits 90', VIEW, [], ('local', 'http://127.0.0.1:11434', 5), app, transport=httpx.MockTransport(handler)))
    assert reply['action']['path'] == '/records/rooms/r1' and reply['action']['version'] == 5
    assert reply['action']['body']['capacity'] == 90


def test_chat_persists_generic_followup_and_never_executes_before_confirmation(environment, monkeypatch):
    from test_workflows import login
    import app.assistant_capabilities as capabilities
    client, factory = environment
    login(client)
    monkeypatch.setenv('JADWAI_AI_ENABLED', 'true')
    monkeypatch.setenv('JADWAI_AI_PROVIDER', 'local')
    seen = []
    async def local(raw, view, history, settings, app, **kwargs):
        seen.append((raw, history, kwargs.get('pending')))
        if len(seen) == 1:
            return {'text': ['What term name should I use?'], 'asking': True, 'pending': {'operation': 'PUT /api/workspace'}, 'conversation': True}
        return {'text': ['Change the term to Spring?'], 'action': {'type': 'website_request', 'method': 'PUT', 'path': '/workspace', 'body': {}, 'version': view['version'], 'label': 'Review and run'}, 'conversation': True}
    monkeypatch.setattr(capabilities, 'converse', local)
    first = client.post('/api/assistant', json={'text': 'Can you adjust our semester configuration?', 'use_model': True}).json()
    second = client.post('/api/assistant', json={'text': 'Spring', 'use_model': True, 'chat_id': first['chat_id']}).json()
    assert seen[1][2] == {'operation': 'PUT /api/workspace'}
    assert any('semester configuration' in h['content'] for h in seen[1][1])
    assert second['action']['type'] == 'website_request'
    assert client.get('/api/workspace').json()['term'] == 'Fall 2026'


def test_coordinator_keeps_running_without_http_requests(monkeypatch):
    import app.chain_coordinator as coordinator
    calls = []
    async def run():
        stop = asyncio.Event()
        def tick(factory):
            calls.append(factory)
            if len(calls) == 2:
                loop.call_soon_threadsafe(stop.set)
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(coordinator, 'advance', tick)
        await coordinator.coordinate(stop, factory='isolated', interval=0.01)
    asyncio.run(run())
    assert calls == ['isolated', 'isolated']


def test_capability_registry_covers_every_noncredential_website_route():
    from app.assistant_capabilities import EXCLUDED
    expected = {method.upper() + ' ' + path for path, methods in app.openapi()['paths'].items()
                if path.startswith('/api/') and not path.startswith(EXCLUDED)
                for method in methods if method in ('get', 'post', 'put', 'patch', 'delete')}
    assert set(catalogue(app)) == expected


def test_common_discussions_preserve_sessions_and_shared_lecture_meaning():
    from app.assistant_explanations import explain
    first = explain('Explain how two free days would affect shared lectures', VIEW)
    assert '4 teaching days' in first and 'none are cancelled' in first
    second = explain('Could we keep their shared lectures fixed, then?', VIEW)
    assert 'locks' in second and 'solver must check' in second


def test_completed_results_keep_ordered_references_but_drop_secrets(environment):
    from test_workflows import login
    from app.models import AssistantChat
    client, factory = environment
    login(client)
    reply = client.post('/api/assistant', json={'text': 'help'}).json()
    result = client.post(f"/api/assistant/chats/{reply['chat_id']}/messages/{reply['message_id']}/done", json={
        'note': ['Two users returned.'], 'confirmation_text': 'yes, do it',
        'result_context': [{'id': 'a', 'name': 'First', 'password': 'private'}, {'id': 'b', 'name': 'Second', 'reset': {'token': 'private'}}]})
    assert result.status_code == 200
    with factory() as db:
        memory = db.get(AssistantChat, reply['chat_id']).state['memory']
        assert memory['recent_results'] == [{'id': 'a', 'name': 'First'}, {'id': 'b', 'name': 'Second'}]
    history = client.get(f"/api/assistant/chats/{reply['chat_id']}").json()['messages']
    assert any(m.get('text') == 'yes, do it' for m in history)


def test_room_programme_restriction_is_not_misrouted_as_assignment_lock():
    sent = []
    def handler(req):
        sent.append(json.loads(req.content))
        result = {'reply': 'Allow only Business Administration in A3.128?', 'ready': True,
                  'arguments': json.dumps({'path': {'kind': 'rooms', 'ident': 'r1'}, 'body': {'reserved_majors': ['Business Administration']}})}
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(result)}})
    reply = asyncio.run(converse('Please restrict room A3.128 to Business Administration only, preserving its other details.', VIEW, [],
                        ('local', 'http://127.0.0.1:11434', 5), app, transport=httpx.MockTransport(handler)))
    assert len(sent) == 1
    assert reply['action']['path'] == '/records/rooms/r1'
    assert reply['action']['body']['reserved_majors'] == ['Business Administration']
    assert reply['action']['body']['capacity'] == 60
    assert set(json.loads(sent[0]['messages'][-1]['content'])['contract']['record_bodies']) == {'rooms'}


def test_arabic_question_answered_in_english_is_rewritten_in_arabic():
    replies = [{'operation': '', 'reply': 'Draft 3 has 212 sessions. Which group do you mean?'},
               {'reply': 'Draft 3 فيها 212 حصة. تقصد أنهي جروب؟'}]
    sent = []
    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(replies.pop(0), ensure_ascii=False)}})
    reply = asyncio.run(converse('الجدول ده زحمة أوي، ممكن تقولي ليه؟', VIEW, [], ('local', 'http://127.0.0.1:11434', 5), app, transport=httpx.MockTransport(handler)))
    assert reply['text'] == ['Draft 3 فيها 212 حصة. تقصد أنهي جروب؟'] and len(sent) == 2
    assert 'Egyptian Arabic' in sent[1]['messages'][0]['content'] and 'Draft 3 has 212' in sent[1]['messages'][1]['content']


def test_language_rewrite_keeps_original_when_not_needed_or_it_fails():
    from app.assistant_capabilities import in_user_language
    settings = ('local', 'http://127.0.0.1:11434', 5)
    def never(req):
        raise AssertionError('no rewrite expected')
    for raw, reply in [('Why is it crowded?', 'Because Draft 3 has 212 sessions.'),
                       ('ليه الجدول زحمة؟', 'عشان Draft 3 فيها 212 حصة.'),
                       ('اشرحلي بالانجليزي', 'It has 212 sessions.')]:
        assert asyncio.run(in_user_language(raw, reply, settings, httpx.MockTransport(never))) == reply
    english = lambda req: httpx.Response(200, json={'done': True, 'message': {'content': json.dumps({'reply': 'Still English.'})}})
    broken = lambda req: httpx.Response(500)
    for handler in (english, broken):
        assert asyncio.run(in_user_language('ليه الجدول زحمة؟', 'It has 212 sessions.', settings, httpx.MockTransport(handler))) == 'It has 212 sessions.'
