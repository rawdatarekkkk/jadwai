import asyncio
import json
import pytest
import httpx
from app.extraction import ExtractionRequest, extract_candidate
from app.local_provider import LocalProvider
from app.openai_provider import INSTRUCTIONS, PROMPT_VERSION, output_schema

ANSWER = '{"decision":"clarify","proposals":[],"clarifications":["which_hours"],"unsupported":[]}'


def request():
    return ExtractionRequest.create('مش عايز محاضرات السبت', {'calendar': {'days': ['Saturday']}}, 23, PROMPT_VERSION, 'proposal-contract-v1')


def run(handler, **options):
    return asyncio.run(extract_candidate(LocalProvider('qwen2.5:7b-instruct', transport=httpx.MockTransport(handler), **options), request(), timeout_seconds=30))


def reply(**changes):
    value = {'model': 'qwen2.5:7b-instruct', 'done': True, 'message': {'role': 'assistant', 'content': ANSWER}, 'prompt_eval_count': 900, 'eval_count': 40}
    value.update(changes)
    return value


def test_same_instructions_and_schema_sent_to_the_local_model():
    def handler(req):
        assert str(req.url) == 'http://127.0.0.1:11434/api/chat'
        body = json.loads(req.content)
        assert body['model'] == 'qwen2.5:7b-instruct' and body['stream'] is False
        assert body['format'] == output_schema() and body['options']['temperature'] == 0
        assert body['messages'][0] == {'role': 'system', 'content': INSTRUCTIONS}
        user = json.loads(body['messages'][1]['content'])
        assert user['requirement'] == 'مش عايز محاضرات السبت' and user['context']['calendar']['days'] == ['Saturday']
        assert 'Authorization' not in req.headers
        return httpx.Response(200, json=reply())
    result = run(handler)
    assert result.status == 'candidate' and result.requires_human_approval
    assert (result.provider, result.model) == ('ollama', 'qwen2.5:7b-instruct')
    assert (result.response_id, result.input_tokens, result.output_tokens) == (None, 900, 40)


@pytest.mark.parametrize('data,status', [
    (reply(done=False), 'incomplete'),
    (reply(message={'role': 'assistant', 'content': ''}), 'invalid_response'),
    (reply(message={'role': 'assistant', 'content': 'not json'}), 'invalid_response'),
    (reply(eval_count=-3), 'candidate'),  # odd counters are dropped, not trusted
])
def test_unfinished_empty_or_broken_answers(data, status):
    assert run(lambda _: httpx.Response(200, json=data)).status == status


@pytest.mark.parametrize('code,status', [(404, 'provider_error'), (500, 'provider_unavailable'), (400, 'provider_error')])
def test_errors_do_not_expose_the_server_body(code, status):
    result = run(lambda _: httpx.Response(code, json={'error': 'private server message'}))
    assert result.status == status and 'private server message' not in repr(result)


def test_ollama_not_running():
    def handler(_):
        raise httpx.ConnectError('refused')
    assert run(handler).status == 'provider_unavailable'


def test_chosen_only_when_enabled_and_set_to_local(monkeypatch):
    monkeypatch.setenv('JADWAI_AI_ENABLED', 'true')
    monkeypatch.delenv('JADWAI_AI_PROVIDER', raising=False)
    with pytest.raises(ValueError):
        LocalProvider.configured()
    monkeypatch.setenv('JADWAI_AI_PROVIDER', 'local')
    monkeypatch.setenv('JADWAI_LOCAL_MODEL', 'llama3.1:8b')
    monkeypatch.setenv('JADWAI_LOCAL_URL', 'http://gpu-box:11434/')
    monkeypatch.setenv('JADWAI_LOCAL_TIMEOUT_SECONDS', '240')
    p = LocalProvider.configured()
    assert (p.model, p.url, p.timeout_seconds) == ('llama3.1:8b', 'http://gpu-box:11434', 240)
    monkeypatch.setenv('JADWAI_LOCAL_TIMEOUT_SECONDS', '2')
    with pytest.raises(ValueError):
        LocalProvider.configured()
    monkeypatch.setenv('JADWAI_AI_ENABLED', 'false')
    monkeypatch.setenv('JADWAI_LOCAL_TIMEOUT_SECONDS', '240')
    with pytest.raises(ValueError):
        LocalProvider.configured()


def test_configuration_reports_the_local_model(monkeypatch):
    from app import model_calls
    monkeypatch.setenv('JADWAI_AI_ENABLED', 'true')
    monkeypatch.setenv('JADWAI_AI_PROVIDER', 'local')
    monkeypatch.setenv('JADWAI_LOCAL_MODEL', 'qwen2.5:7b-instruct')
    assert model_calls.configuration(user=None) == {'model': 'qwen2.5:7b-instruct', 'provider': 'local', 'enabled': True, 'prompt_version': PROMPT_VERSION}
    monkeypatch.delenv('JADWAI_AI_PROVIDER')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert model_calls.configuration(user=None)['provider'] == 'openai'


def test_large_workspace_sends_only_the_records_the_text_names():
    from app.local_provider import relevant_context
    many = [{'id': f'i{n}', 'kind': 'instructors', 'data': {'name': f'Dr. Person{n} Example', 'code': f'P{n}', 'email': 'x@y'}} for n in range(200)]
    many += [{'id': 'a1', 'kind': 'instructors', 'data': {'name': 'Dr. Ahmed Hassan', 'code': 'AH'}},
             {'id': 'a2', 'kind': 'instructors', 'data': {'name': 'Dr. Ahmed Fawzy', 'code': 'AF'}},
             {'id': 'r1', 'kind': 'rooms', 'data': {'name': 'Data Science Lab', 'code': 'C7.201'}}]
    ctx = {'records': many, 'calendar': {'days': ['Sunday']}}
    exact = relevant_context('Dr. Ahmed Hassan cannot use C7.201 on Sunday', ctx)
    assert {r['id'] for r in exact['records']} == {'a1', 'r1'} and exact['calendar'] == ctx['calendar']
    unsure = relevant_context('Ahmed cannot teach on Sunday', ctx)
    assert {r['id'] for r in unsure['records']} == {'a1', 'a2'}  # both, so the model can ask which
    small = relevant_context('anything', {'records': many[:3], 'calendar': {}})
    assert len(small['records']) == 3 and 'email' not in small['records'][0]['data']


def test_invalid_semantics_get_one_local_correction_before_review():
    calls = []
    context = {'records': [{'id': 'i', 'kind': 'instructors', 'data': {'name': 'Sara'}}],
               'calendar': {'days': ['Sunday'], 'start_hour': 8, 'end_hour': 18}}
    original = {'decision': 'ready', 'proposals': [], 'clarifications': [], 'unsupported': []}
    fixed = {'decision': 'clarify', 'proposals': [], 'clarifications': ['time_required'], 'unsupported': []}
    def handler(req):
        calls.append(json.loads(req.content))
        answer = original if len(calls) == 1 else fixed
        return httpx.Response(200, json=reply(message={'content': json.dumps(answer)}))
    provider = LocalProvider(transport=httpx.MockTransport(handler))
    req = ExtractionRequest.create('Sara is unavailable', context, 1, PROMPT_VERSION, 'proposal-contract-v1')
    result = asyncio.run(extract_candidate(provider, req, timeout_seconds=5))
    assert len(calls) == 2 and json.loads(result.candidate_json) == fixed
    assert 'validation_errors' in calls[1]['messages'][-1]['content']
    assert result.requires_human_approval
