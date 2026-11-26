import asyncio,json
from uuid import uuid4
from sqlalchemy import select
from app.main import app
from app.model_calls import provider
from app.extraction import DeterministicProvider
from app.models import Workspace,User,ExtractionProposal,ExtractionJob
from test_workflows import login,version


def output(client):
    day=client.get('/api/workspace').json()['calendar']['days'][0]
    return json.dumps({'decision':'ready','proposals':[{'kind':'rule','data':{'title':'Synthetic model test','type':'unavailable','instructor_id':'teacher','day':day,'start_hour':9,'end_hour':11,'strength':'mandatory'}}],'clarifications':[],'unsupported':[]})


def test_configuration_disabled_and_permissions(environment,monkeypatch):
    client,_=environment;monkeypatch.delenv('JADWAI_AI_ENABLED',raising=False);monkeypatch.delenv('JADWAI_AI_PROVIDER',raising=False)
    assert client.get('/api/model-calls/configuration').status_code==401
    login(client)
    assert client.get('/api/model-calls/configuration').json()=={'model':'gpt-5.4-mini','provider':'openai','enabled':False,'prompt_version':'jai-rules-v4'}
    assert client.post('/api/model-calls',json={'request_key':str(uuid4()),'text':'test'},headers=version(client)).status_code==503
    client.post('/api/auth/logout');login(client,'viewer@example.test')
    assert client.get('/api/model-calls/configuration').status_code==403


def test_completed_call_retry_does_not_call_provider_or_create_rules_twice(environment):
    client,factory=environment;login(client)
    class Counting(DeterministicProvider):
        calls=0
        async def extract(self,request):self.calls+=1;return self.response
    adapter=Counting(output(client));app.dependency_overrides[provider]=lambda:adapter
    body={'request_key':str(uuid4()),'text':'Synthetic Arabic عربي'}
    result=client.post('/api/model-calls',json=body,headers=version(client))
    assert result.status_code==201,result.text
    assert result.json()['status']=='completed' and result.json()['proposal_id']
    again=client.post('/api/model-calls',json=body)
    assert again.json()==result.json() and adapter.calls==1
    assert client.get('/api/model-calls/by-key/'+body['request_key']).json()==result.json()
    assert not client.get('/api/workspace').json()['rules']
    assert client.post('/api/model-calls',json={**body,'text':'different'}).status_code==409


def test_inputs_changed_during_await_reject_late_output(environment):
    client,factory=environment;login(client)
    class Changing(DeterministicProvider):
        async def extract(self,request):
            await asyncio.sleep(0)
            with factory.begin() as db:db.get(Workspace,1).version+=1
            return self.response
    adapter=Changing(output(client))
    app.dependency_overrides[provider]=lambda:adapter
    result=client.post('/api/model-calls',json={'request_key':str(uuid4()),'text':'test'},headers=version(client))
    assert result.json()['status']=='stale',result.text
    with factory() as db:assert not db.scalars(select(ExtractionProposal)).all()


def test_cancelled_call_never_accepts_late_candidate(environment):
    client,factory=environment;login(client)
    class Cancelling(DeterministicProvider):
        async def extract(self,request):
            with factory.begin() as db:db.scalar(select(ExtractionJob)).status='cancelled'
            return self.response
    adapter=Cancelling(output(client))
    app.dependency_overrides[provider]=lambda:adapter
    result=client.post('/api/model-calls',json={'request_key':str(uuid4()),'text':'test'},headers=version(client))
    assert result.json()['status']=='cancelled'
    assert client.post('/api/model-calls/'+result.json()['id']+'/cancel').json()['status']=='cancelled'
    with factory() as db:assert not db.scalars(select(ExtractionProposal)).all()


def test_revoked_administrator_cannot_save_completion(environment):
    client,factory=environment;login(client)
    class Revoking(DeterministicProvider):
        async def extract(self,request):
            with factory.begin() as db:db.get(User,'admin').active=False
            return self.response
    adapter=Revoking(output(client))
    app.dependency_overrides[provider]=lambda:adapter
    result=client.post('/api/model-calls',json={'request_key':str(uuid4()),'text':'test'},headers=version(client))
    assert result.status_code==403
    with factory() as db:assert not db.scalars(select(ExtractionProposal)).all()


def test_call_cut_off_by_a_restart_does_not_block_later_calls(environment):
    from datetime import timedelta
    from app.models import utcnow
    client,factory=environment;login(client)
    adapter=DeterministicProvider(output(client));app.dependency_overrides[provider]=lambda:adapter
    with factory.begin() as db:
        admin=db.scalar(select(User).where(User.role=='administrator'))
        db.add(ExtractionJob(id=str(uuid4()),request_key=str(uuid4()),submitted_by=admin.id,input_sha256='x'*64,status='running',created_at=utcnow()-timedelta(hours=2)))
        db.add(ExtractionJob(id=str(uuid4()),request_key=str(uuid4()),submitted_by=admin.id,input_sha256='y'*64,status='running',created_at=utcnow()))
    # A recent running call still blocks a second one.
    assert client.post('/api/model-calls',json={'request_key':str(uuid4()),'text':'one'},headers=version(client)).json()['detail']=='model_call_in_progress'
    with factory.begin() as db:
        for job in db.scalars(select(ExtractionJob).where(ExtractionJob.input_sha256=='y'*64)):job.created_at=utcnow()-timedelta(hours=1)
    result=client.post('/api/model-calls',json={'request_key':str(uuid4()),'text':'two'},headers=version(client))
    assert result.status_code==201 and result.json()['status']=='completed',result.text
    with factory() as db:
        assert {j.status for j in db.scalars(select(ExtractionJob).where(ExtractionJob.input_sha256.in_(['x'*64,'y'*64])))}=={'abandoned'}
