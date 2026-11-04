import asyncio
import json
from dataclasses import replace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.extraction import ExtractionRequest, DeterministicProvider, extract_candidate
from app.extraction_completion import persist_completion
from app.models import Workspace, User, ExtractionProposal
from app.proposals import context
from test_workflows import login, version


def execution(factory, text='لا توجد محاضرات في هذا الوقت'):
    with factory() as db:
        ws = db.get(Workspace, 1); snapshot = context(db, ws)
        request = ExtractionRequest.create(text, snapshot, ws.version, 'synthetic-test-v1', 'proposal-contract-v1')
        output = {'decision':'ready','proposals':[{'kind':'rule','data':{
            'title':'Synthetic completion test','type':'unavailable','instructor_id':'teacher',
            'day':ws.days[0],'start_hour':9,'end_hour':11,'strength':'mandatory'}}],
            'clarifications':[],'unsupported':[]}
    result = asyncio.run(extract_candidate(DeterministicProvider(json.dumps(output)), request))
    return request, result


def save(factory, request, result, key=None):
    with factory.begin() as db:
        row = persist_completion(db, actor_id='admin', request_key=key or uuid4(), request=request, result=result)
        return row.id


@pytest.mark.parametrize('text',['No classes in this period','لا محاضرات في هذا الوقت','مش عايز محاضرات في الوقت ده','No lectures في الوقت ده'])
def test_multilingual_completion_reaches_separate_manual_approval(environment,text):
    client, factory = environment; login(client)
    request, result = execution(factory, text); key = uuid4()
    ident = save(factory, request, result, key)
    assert save(factory, request, result, key) == ident
    saved = client.get('/api/proposals').json()['proposals'][0]
    assert saved['record']['text'] == text
    assert saved['record']['execution_kind'] == 'test_double'
    assert saved['record']['execution']['input_sha256'] == request.input_sha256
    assert not client.get('/api/workspace').json()['rules']
    converted = client.post(f'/api/proposals/{ident}/review',json={
        'request_key':str(uuid4()),'action':'create_drafts','rationale':'Synthetic workflow only.'},headers=version(client))
    assert converted.status_code == 201, converted.text
    rule_id = converted.json()['rule_ids'][0]
    assert client.get('/api/workspace').json()['rules'][0]['status'] == 'draft'
    assert client.post(f'/api/rules/{rule_id}/approve',headers=version(client)).status_code == 200


@pytest.mark.parametrize('change',['version','calendar','revoked','role'])
def test_late_completion_rechecks_inputs_and_actor(environment,change):
    _, factory = environment; request, result = execution(factory)
    with factory.begin() as db:
        if change=='version': db.get(Workspace,1).version += 1
        elif change=='calendar': db.get(Workspace,1).end_hour = 16
        elif change=='revoked': db.get(User,'admin').active = False
        else: db.get(User,'admin').role = 'viewer'
    with pytest.raises(HTTPException) as error: save(factory, request, result)
    assert error.value.status_code == (409 if change in ('version','calendar') else 403)
    with factory() as db: assert not db.scalars(select(ExtractionProposal)).all()


@pytest.mark.parametrize('change',['timeout','hash','raw','semantic','schema'])
def test_failed_or_unbound_completions_never_create_proposals(environment,change):
    _, factory = environment; request, result = execution(factory)
    if change=='timeout': result=replace(result,status='timeout')
    elif change=='hash': result=replace(result,input_sha256='bad')
    elif change=='raw': result=replace(result,raw_response='{}')
    elif change=='schema': request=replace(request,schema_version='other');result=replace(result,schema_version='other',input_sha256=request.input_sha256)
    else:
        output=json.loads(result.candidate_json);output['proposals'][0]['data']['instructor_id']='invented'
        from app.extraction import parse_candidate
        raw=json.dumps(output);result=replace(result,raw_response=raw,candidate_json=parse_candidate(raw))
    with pytest.raises(HTTPException) as error: save(factory, request, result)
    assert error.value.status_code == 422
    with factory() as db: assert not db.scalars(select(ExtractionProposal)).all()


def test_retry_cannot_replace_execution_evidence(environment):
    _,factory=environment;request,result=execution(factory);key=uuid4()
    save(factory,request,result,key)
    with pytest.raises(HTTPException) as error:save(factory,request,replace(result,model='different'),key)
    assert error.value.status_code==409
