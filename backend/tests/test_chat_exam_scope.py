from copy import deepcopy
from app.assistant import understand,answer
from test_assistant import VIEW
from test_workflows import login,version


def scoped_view():
    v=deepcopy(VIEW)
    v['catalog']=[{'id':'ba-course','name':'Accounting','code':'ACC','group_ids':['g7']},{'id':'it-course','name':'Networks','code':'NET','group_ids':['g8']},{'id':'shared','name':'English','code':'ENG','group_ids':['g7','g8']}]
    return v


def test_ba_scope_survives_date_followup_and_keeps_shared_courses():
    v=scoped_view();first=understand('create a midterm schedule for BA',v,None)
    reply=answer(first,v,False);first['asking']=reply['asking']
    next_=understand('from dec 20 to 31 dec',v,first)
    result=answer(next_,v,False)
    assert result['action']['body']['course_ids']==['ba-course','shared']
    assert result['action']['body']['start_date'].endswith('-12-20')
    assert 'Business Administration' in result['text'][0]
    assert understand('publish it',v,next_)['slots']['exams']


def test_missing_scoped_courses_never_generate_all_courses():
    v=scoped_view();v['catalog']=[]
    result=answer(understand('create midterm schedule for BA from 20 dec to 31 dec',v,None),v,False)
    assert result.get('asking') and not result.get('action')


def test_api_scope_filters_exams_and_rejects_unknown_course(environment):
    from app.models import CourseCatalog
    client,factory=environment;login(client)
    with factory.begin() as db:
        for ident in ('selected','other'):
            db.add(CourseCatalog(id=ident,name=ident,code=ident,eligibility={'lecture':[],'tutorial':[],'lab':[]},group_ids=[],expected_students=20,source_info={'program_semesters':[{'faculty_section':'BUSINESS','program_or_cohort':ident,'semester':1}]}))
    body={'kind':'midterm','start_date':'2026-12-20','end_date':'2026-12-31','use_halls':False,'course_ids':['selected']}
    result=client.post('/api/exam-schedules',json=body,headers=version(client))
    assert result.status_code==201,result.text
    assert {c['course_id'] for c in result.json()['snapshot']['courses']}=={'selected'}
    body['course_ids']=['unknown']
    assert client.post('/api/exam-schedules',json=body,headers=version(client)).json()['detail']=='invalid_exam_scope'


def test_exam_unpublication_is_an_executable_chat_action():
    v=scoped_view();v['exam_run']={'id':'exam1','published':True}
    result=answer(understand('unpublish the exam timetable',v,None),v,False)
    assert result['action']['type']=='unpublish' and result['action']['what']=='exams'


def test_unknown_exam_scope_is_clarified_instead_of_widened():
    v=scoped_view()
    first=understand('create midterm schedule for unknownprogramme',v,None)
    result=answer(first,v,False)
    assert result.get('asking') and not result.get('action')
    assert 'unknownprogramme' in result['text'][0]


def test_chat_uses_local_constraint_interpretation_without_creating_rules(environment,monkeypatch):
    import json
    from sqlalchemy import select,func
    from app.models import Rule
    from app.local_provider import LocalProvider
    from app.extraction import ProviderResponse
    client,factory=environment;login(client)
    monkeypatch.setenv('JADWAI_AI_ENABLED','true');monkeypatch.setenv('JADWAI_AI_PROVIDER','local')
    candidate={'decision':'ready','proposals':[{'kind':'rule','data':{'title':'Later tutorials','type':'teaching_preferred','strength':'preferred','day':None,'start_hour':10.0,'end_hour':18.0,'params':{'activity_types':['tutorial']}}}],'clarifications':[],'unsupported':[]}
    async def extract(self,request):return ProviderResponse(json.dumps(candidate))
    monkeypatch.setattr(LocalProvider,'extract',extract)
    body={'text':'prefer tutorials after ten','previous':{}}
    first=client.post('/api/assistant',json=body).json()
    assert first['retry_with_model'] and not first['action']
    reply=client.post('/api/assistant',json={**body,'use_model':True}).json()
    assert reply['source']=='local-model' and reply['action']['rules'][0]['strength']=='preferred'
    with factory() as db:assert db.scalar(select(func.count()).select_from(Rule))==0


def test_explicit_exam_options_are_not_silently_ignored():
    v=scoped_view();result=answer(understand('create final exam schedule from 20 dec to 31 dec include second chances include fridays without halls with 2 exams per day',v,None),v,False)
    body=result['action']['body']
    assert body['skip']==[] and body['exclude_fridays'] is False and body['use_halls'] is False
    assert body['max_exams_per_cohort_day']==2
    assert 'including Fridays' in result['text'][0]


def test_exam_focus_survives_pdf_and_publish_followups():
    from app.assistant_context import with_context
    v=scoped_view();v['exam_run']={'id':'selected-exam','status':'completed','kind':'midterm','published':False,'halls':True,'stale':False}
    memory={'run':'weekly','exam_run':'selected-exam','schedule_focus':{'kind':'exams','id':'selected-exam'}}
    pdf=with_context('save pdf',understand('save pdf',v,None),memory)
    assert answer(pdf,v,False)['action']['url']=='/api/exam-schedules/selected-exam/exams.pdf'
    publish=with_context('publish it',understand('publish it',v,pdf),memory)
    action=answer(publish,v,False)['action']
    assert action['type']=='publish' and action['what']=='exams' and action['run_id']=='selected-exam'
    weekly=with_context('save weekly schedule pdf',understand('save weekly schedule pdf',v,None),memory)
    assert weekly['intent']=='download_pdf' and weekly['slots']['schedule_kind']=='teaching'


def test_incomplete_exam_cannot_offer_pdf():
    v=scoped_view();v['exam_run']={'id':'failed','status':'infeasible'}
    result=answer({'intent':'exam_pdf','slots':{}},v,False)
    assert not result.get('action')


def test_chat_exports_selected_exam_instead_of_latest(environment):
    from app.models import ExamRun,AssistantChat
    client,factory=environment;login(client)
    with factory.begin() as db:
        for ident in ('selected-exam','newer-exam'):
            db.add(ExamRun(id=ident,input_version=1,snapshot={'settings':{'kind':'midterm','use_halls':True},'halls':[]},result={'status':'completed','assignments':[]}))
        db.add(AssistantChat(id='exam-chat',user_id='admin',title='Exam chat',state={'memory':{'exam_run':'selected-exam','schedule_focus':{'kind':'exams','id':'selected-exam'}}}))
    assert client.get('/api/exam-schedules/selected-exam').json()['id']=='selected-exam'
    result=client.post('/api/assistant',json={'text':'save pdf','chat_id':'exam-chat'}).json()
    assert result['action']['url']=='/api/exam-schedules/selected-exam/exams.pdf'
    result=client.post('/api/assistant',json={'text':'publish it','chat_id':'exam-chat'}).json()
    assert result['action']['what']=='exams' and result['action']['run_id']=='selected-exam'
    result=client.post('/api/assistant',json={'text':'save pdf','chat_id':'exam-chat','screen':{'page':'exams','run_id':'newer-exam','query':'Accounting'}}).json()
    assert result['action']['url']=='/api/exam-schedules/newer-exam/exams.pdf?q=Accounting'
