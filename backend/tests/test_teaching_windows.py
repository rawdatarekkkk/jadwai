from copy import deepcopy
import json
import asyncio
import httpx
import pytest
from app.solver import generate
from app.validation import validate_schedule
from app.validation_details import preference_penalty
from app.schemas import RuleInput
from app.rule_validation import rule_error
from app.local_provider import LocalProvider
from app.extraction import ExtractionRequest
from app.openai_provider import PROMPT_VERSION
from test_schedules import example


def snapshot(soft=True):
    s=example();s['records'][4]['sessions']=1
    s['rules']=[{'id':'w','status':'approved','type':'teaching_preferred' if soft else 'teaching_allowed','strength':'preferred' if soft else 'mandatory','day':None,'start_hour':10.0,'end_hour':12.0,'params':{'activity_types':['lecture']}}]
    return s


def rows():
    return [dict(activity_id=a,occurrence=0,day='Sunday',start_minute=start,end_minute=end,instructor_id='t',room_id='r') for a,start,end in [('a',480,540),('b',540,630)]]


def test_soft_can_be_violated_with_independent_penalty_but_hard_cannot():
    s=snapshot();r=generate(s,fixed_assignments=rows())
    assert r['status']=='completed' and r['preference_penalty']==1
    assert validate_schedule(s,rows())['passed']
    assert preference_penalty(s,rows())['total']==1
    hard=snapshot(False)
    assert generate(hard,fixed_assignments=rows())['status']=='infeasible'
    assert 'approved_teaching_windows' in validate_schedule(hard,rows())['errors']


def test_optimization_respects_type_and_avoids_window_penalty_when_possible():
    s=snapshot();result=generate(s)
    assert result['status']=='completed'
    assert result['preference_penalty']==0
    assert preference_penalty(s,result['assignments'])['total']==0
    assert next(a for a in result['assignments'] if a['activity_id']=='a')['start_minute']>=600


def test_instructor_and_teaching_preferences_both_count():
    s=snapshot();s['rules'].append({'id':'i','status':'approved','type':'preferred_period','instructor_id':'t','strength':'preferred','day':None,'start_hour':11.0,'end_hour':12.0})
    r=generate(s,fixed_assignments=rows())
    assert r['status']=='completed' and r['preference_penalty']==3
    assert preference_penalty(s,rows())['total']==3


def test_rule_strength_and_target_validation():
    for soft in (True,False):
        s=snapshot(soft);body=RuleInput.model_validate({'title':'Teaching time',**{k:v for k,v in s['rules'][0].items() if k not in ('id','status')}})
        assert rule_error(body,lambda k:None,s['calendar']) is None
        body.strength='mandatory' if soft else 'preferred'
        assert rule_error(body,lambda k:None,s['calendar'])=='invalid_strength'


def test_explicit_preference_cannot_become_a_hard_rule():
    candidate={'decision':'ready','proposals':[{'kind':'rule','data':{'title':'Wrong strength','type':'teaching_allowed','day':None,'start_hour':10.0,'end_hour':12.0,'strength':'mandatory','params':{'activity_types':['lecture']}}}],'clarifications':[],'unsupported':[]}
    async def handler(request):return httpx.Response(200,json={'done':True,'message':{'content':json.dumps(candidate)}})
    s=snapshot();context={'records':[{'id':r['id'],'kind':r['kind'],'data':r} for r in s['records']],'calendar':s['calendar']}
    request=ExtractionRequest.create('preferred: avoid early lectures',context,1,PROMPT_VERSION,'proposal-contract-v1')
    result=asyncio.run(LocalProvider('model','http://127.0.0.1:11434',transport=httpx.MockTransport(handler)).extract(request))
    out=json.loads(result.text)
    assert out['decision']=='clarify' and out['proposals']==[]


def test_persistence_and_approval_are_separate(environment):
    from test_workflows import login,version
    client,_=environment;login(client)
    rule=snapshot()['rules'][0];body={'title':'Time preference',**{k:v for k,v in rule.items() if k not in ('id','status')}}
    result=client.post('/api/rules',json=body,headers=version(client))
    assert result.status_code==201,result.text
    ident=result.json()['id']
    rule=next(r for r in client.get('/api/workspace').json()['rules'] if r['id']==ident)
    assert rule['status']=='draft' and rule['strength']=='preferred'
    assert client.post('/api/rules/'+ident+'/approve',headers=version(client)).status_code==200


def test_statistics_count_teaching_preferences_without_instructor_target():
    from test_statistics import measured
    from app.statistics import build_statistics
    s,result=measured();s['rules'].append({'id':'global','title':'Later lectures','status':'approved','type':'teaching_preferred','strength':'preferred','day':None,'start_hour':10.0,'end_hour':12.0,'params':{'activity_types':['lecture']}})
    stats=build_statistics(s,result)
    assert stats['preferences']['approved_rules']==3
    assert stats['preferences']['unsatisfied_sessions']==3
    assert any(p['id']=='global' and p['unsatisfied_sessions']==2 for p in stats['preferences']['per_rule'])


def test_different_type_selectors_do_not_relax_each_other():
    s=snapshot(False)
    s['rules'].append({'id':'all','status':'approved','type':'teaching_allowed','strength':'mandatory','day':None,'start_hour':8.0,'end_hour':12.0,'params':{'activity_types':['lecture','tutorial','lab']}})
    assert generate(s,fixed_assignments=rows())['status']=='infeasible'
    assert 'approved_teaching_windows' in validate_schedule(s,rows())['errors']


def test_semantic_frame_compiles_calendar_slot_and_does_not_expand_lecture_scope():
    from app.teaching_language import compile_frame
    frame={'kind':'teaching_window','activity_types':['lecture'],'strength':'preferred','mode':'avoid','days':[],'slot_number':1,'start_hour':None,'end_hour':None,'question':''}
    calendar={'days':['Sunday','Monday'],'start_hour':8,'end_hour':18,'period_minutes':90,'teaching_periods':[{'start':510,'end':600},{'start':615,'end':705}]}
    result=compile_frame(frame,'Ideally avoid lectures in the opening period',calendar)
    assert result['decision']=='ready'
    assert {(p['data']['start_hour'],p['data']['end_hour']) for p in result['proposals']}=={(10.0,18.0)}
    assert all(p['data']['strength']=='preferred' and p['data']['params']['activity_types']==['lecture'] for p in result['proposals'])
    frame['strength']='mandatory'
    hard=compile_frame(frame,'No lectures in the first period',calendar)
    assert all(p['data']['type']=='teaching_allowed' for p in hard['proposals'])


def test_local_model_frame_uses_same_transport_and_returns_validated_rules():
    from app.teaching_language import FRAME
    seen=[]
    def handler(request):
        payload=json.loads(request.content);seen.append(payload)
        frame={'kind':'teaching_window','activity_types':['lecture'],'strength':'preferred','mode':'avoid','days':[],'slot_number':1,'start_hour':None,'end_hour':None,'question':''}
        return httpx.Response(200,json={'done':True,'message':{'content':json.dumps(frame)},'prompt_eval_count':20,'eval_count':30})
    s=snapshot();s['calendar']['period_minutes']=60
    context={'records':[],'calendar':s['calendar']}
    req=ExtractionRequest.create('Ideally avoid lectures in the first period',context,1,PROMPT_VERSION,'proposal-contract-v1')
    result=asyncio.run(LocalProvider(transport=httpx.MockTransport(handler)).extract(req))
    output=json.loads(result.text)
    assert seen[0]['format']==FRAME and output['decision']=='ready'
    assert output['proposals'][0]['data']['start_hour']==9.0
    assert output['proposals'][0]['data']['strength']=='preferred'
