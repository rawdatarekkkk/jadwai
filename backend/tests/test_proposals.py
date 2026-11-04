from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from app.models import Workspace
from test_workflows import login, version


def candidate(client):
    ws = client.get('/api/workspace').json()
    return {'request_key': str(uuid4()), 'text': 'No teaching during this period', 'output': {
        'decision': 'ready', 'proposals': [{'kind': 'rule', 'data': {
            'title': 'Imported unavailable period', 'type': 'unavailable', 'instructor_id': 'teacher',
            'day': ws['calendar']['days'][0], 'start_hour': 9, 'end_hour': 11, 'strength': 'mandatory',
        }}], 'clarifications': [], 'unsupported': []}}


def submit(client, body=None):
    response = client.post('/api/proposals', json=body or candidate(client), headers=version(client))
    assert response.status_code == 201, response.text
    return response.json()


def review_body(action='create_drafts'):
    return {'request_key': str(uuid4()), 'action': action, 'rationale': 'Synthetic administrator workflow test.'}


def test_import_review_and_manual_approval_are_separate_idempotent_actions(environment):
    client, factory = environment; login(client)
    before = client.get('/api/workspace').json()
    body = candidate(client); row = submit(client, body)
    assert row['record']['origin'] == 'administrator_import'
    assert not row['record']['model_execution_verified']
    assert row['record']['text'] == body['text'] and row['record']['output'] == body['output']
    assert client.get('/api/workspace').json()['version'] == before['version']
    assert submit(client, body)['id'] == row['id']
    assert client.post('/api/proposals', json={**body, 'text': 'different'}, headers=version(client)).status_code == 409
    payload = review_body(); url = '/api/proposals/' + row['id'] + '/review'
    response = client.post(url, json=payload, headers=version(client))
    assert response.status_code == 201, response.text
    result = response.json(); assert not result['rules_approved'] and len(result['rule_ids']) == 1
    after = client.get('/api/workspace').json()
    rules = [r for r in after['rules'] if r['id'] in result['rule_ids']]
    assert len(rules) == 1 and rules[0]['status'] == 'draft'
    assert after['version'] == before['version'] + 1
    assert client.post(url, json=payload, headers={'If-Match': '"0"'}).json()['id'] == result['id']
    assert len(client.get('/api/workspace').json()['rules']) == len(after['rules'])
    assert client.post(url, json=review_body(), headers=version(client)).status_code == 409
    approved = client.post('/api/rules/' + result['rule_ids'][0] + '/approve', headers=version(client))
    assert approved.status_code == 200
    for table in ('extraction_proposal', 'extraction_proposal_review'):
        for sql in (f'DELETE FROM {table}', f'TRUNCATE {table}', f"UPDATE {table} SET input_sha256='changed'"):
            with pytest.raises(DBAPIError):
                with factory.begin() as db: db.execute(text(sql))


def test_stale_proposal_cannot_create_drafts_but_can_be_dismissed(environment):
    client, factory = environment; login(client)
    row = submit(client)
    with factory.begin() as db: db.get(Workspace, 1).version += 1
    assert client.get('/api/proposals').json()['proposals'][0]['stale']
    url = '/api/proposals/' + row['id'] + '/review'
    result = client.post(url, json=review_body(), headers=version(client))
    assert result.status_code == 409 and result.json()['detail'] == 'stale_proposal'
    assert not client.get('/api/workspace').json()['rules']
    result = client.post(url, json=review_body('dismiss'), headers=version(client))
    assert result.status_code == 201 and result.json()['rule_ids'] == []


def test_clarification_requires_valid_recorded_correction(environment):
    client, _ = environment; login(client)
    body = candidate(client); original = deepcopy(body['output'])
    body['output'].update(decision='clarify', clarifications=['which_period'])
    row = submit(client, body); url = '/api/proposals/' + row['id'] + '/review'
    assert client.post(url, json=review_body(), headers=version(client)).status_code == 422
    invalid = review_body(); invalid['corrected_output'] = deepcopy(original)
    invalid['corrected_output']['proposals'][0]['data']['instructor_id'] = 'invented'
    assert client.post(url, json=invalid, headers=version(client)).status_code == 422
    corrected = review_body(); corrected['corrected_output'] = original
    result = client.post(url, json=corrected, headers=version(client))
    assert result.status_code == 201
    saved = client.get('/api/proposals').json()['proposals'][0]
    assert saved['record']['output']['decision'] == 'clarify'
    assert saved['review']['record']['corrected_output'] == original


def test_access_and_concurrency_preconditions(environment):
    client, _ = environment
    assert client.get('/api/proposals').status_code == 401
    login(client); body = candidate(client)
    assert client.post('/api/proposals', json=body).status_code == 409
    invalid = deepcopy(body); invalid['output']['proposals'][0]['data']['instructor_id'] = 'invented'
    assert client.post('/api/proposals', json=invalid, headers=version(client)).status_code == 422
    assert not client.get('/api/proposals').json()['proposals']
    client.post('/api/auth/logout'); login(client, 'viewer@example.test')
    assert client.get('/api/proposals').status_code == 403
    assert client.post('/api/proposals', json=body).status_code == 403
    assert client.post('/api/proposals/' + str(uuid4()) + '/review', json=review_body()).status_code == 403


def test_nonfinite_and_oversized_imports_are_rejected(environment):
    import json
    client, _ = environment; login(client)
    body = candidate(client); body['output']['extra'] = float('nan')
    result = client.post('/api/proposals', content=json.dumps(body), headers={**version(client), 'Content-Type': 'application/json'})
    assert result.status_code == 422
    body = candidate(client); body['output']['extra'] = 'x' * 1000000
    assert client.post('/api/proposals', json=body, headers=version(client)).status_code == 413
    assert not client.get('/api/proposals').json()['proposals']
