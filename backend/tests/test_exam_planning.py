from copy import deepcopy
from app.exam_planning import generate_exam_draft,validate_exam_draft,course_inputs
from app.exams import ExamInput
from app.models import CourseCatalog
from pydantic import ValidationError
import pytest


def sample():
 return {'dates':['2026-10-20','2026-10-21'],'max_exams_per_cohort_day':1,'missing_cohort_codes':[],'courses':[{'id':'a','code':'A','name':'A','participants':['same-cohort'],'programs':[]},{'id':'b','code':'B','name':'B','participants':['same-cohort'],'programs':[]}]}

def test_two_hours_and_cohort_daily_limit():
 snap=sample();result=generate_exam_draft(snap)
 assert result['status']=='completed' and result['validation']['passed']
 assert len({a['date'] for a in result['assignments']})==2
 assert all(a['duration_minutes']==120 for a in result['assignments'])
 rows=deepcopy(result['assignments']);rows[1]['date']=rows[0]['date']
 assert 'cohort_daily_limit' in validate_exam_draft(snap,rows)['errors']
 rows[0]['duration_minutes']=90
 assert 'exam_times' in validate_exam_draft(snap,rows)['errors']
 assert not validate_exam_draft(snap,rows[:1])['passed']

def test_infeasible_and_missing_cohorts():
 snap=sample();snap['dates']=['2026-10-20']
 assert generate_exam_draft(snap)['reason']=='not_enough_days'
 snap['missing_cohort_codes']=['A']
 assert generate_exam_draft(snap)['reason']=='missing_cohorts'

def test_general_business_courses_share_specialization_cohorts():
 rows=[]
 for ident,program in [('a','Business Administration Core'),('b','Business Administration - Digital Marketing')]:
  rows.append(CourseCatalog(id=ident,name=ident,code=ident,group_ids=[],source_info={'program_semesters':[{'faculty_section':'BUSINESS ADMINISTRATION','program_or_cohort':program,'semester':5}]}))
 courses,missing=course_inputs(rows)
 assert not missing and set(courses[0]['participants'])&set(courses[1]['participants'])

def test_bounded_exam_period():
 with pytest.raises(ValidationError):ExamInput(start_date='2026-10-31',end_date='2026-10-20')
 with pytest.raises(ValidationError):ExamInput(start_date='2026-10-20',end_date='2027-10-20')


def test_saved_exam_api_uses_dates_and_excludes_fridays(environment):
 from test_workflows import login,version
 client,factory=environment;login(client)
 with factory.begin() as db:
  db.add(CourseCatalog(id='exam-course',name='Algorithms',code='ALG',eligibility={'lecture':[],'tutorial':[],'lab':[]},group_ids=[],source_info={'program_semesters':[{'faculty_section':'INFORMATICS','program_or_cohort':'Computer Science','semester':3}]}))
 response=client.post('/api/exam-schedules',headers=version(client),json={'start_date':'2026-10-20','end_date':'2026-10-31','exclude_fridays':True,'use_halls':False})
 assert response.status_code==201,response.text
 run=response.json()
 assert run['result']['status']=='completed' and len(run['result']['assignments'])==1
 assert '2026-10-23' not in run['snapshot']['dates'] and '2026-10-30' not in run['snapshot']['dates']
 assert client.get('/api/exam-schedules').json()[0]['id']==run['id']
 examples=client.post('/api/exam-schedules/feasibility-tests')
 assert examples.status_code==200 and all(c['verified'] for c in examples.json())
 assert len(client.get('/api/exam-schedules').json())==1
 exported=client.get('/api/exam-schedules/'+run['id']+'/export')
 assert exported.status_code==200 and 'ALG' in exported.text and 'Draft: dates and times only' in exported.text
 assert client.post('/api/exam-schedules',headers={'If-Match':'"0"'},json={}).status_code==409
 client.post('/api/auth/logout');login(client,'viewer@example.test')
 assert client.get('/api/exam-schedules').status_code==403
 assert client.post('/api/exam-schedules/feasibility-tests').status_code==403


def test_unknown_semester_exam_conflicts_with_each_cohort_without_merging_known_cohorts():
 rows=[]
 for ident,semester in [('third',3),('fifth',5),('unknown',None)]:
  rows.append(CourseCatalog(id=ident,name=ident,code=ident,group_ids=[],source_info={'program_semesters':[{'faculty_section':'ENGINEERING','program_or_cohort':'Engineering-Manufacturing Engineering','semester':semester}]}))
 courses,_=course_inputs(rows)
 third,fifth,unknown=[set(c['participants']) for c in courses]
 assert not third&fifth
 assert unknown&third and unknown&fifth


def test_recommendations_have_correct_capacity_and_verified_examples():
 from app.exam_planning import feasibility_test_cases
 snap=sample();snap['dates']=['2026-10-20']
 result=generate_exam_draft(snap)
 extension=next(r for r in result['recommendations'] if r['action']=='extend_period')
 assert extension['required_days']==2 and extension['additional_days']==1
 raised=next(r for r in result['recommendations'] if r['action']=='raise_daily_limit')
 assert raised['daily_limit']==2
 snap['dates']=[]
 result=generate_exam_draft(snap)
 assert result['status']=='infeasible'
 assert not any(r['action']=='raise_daily_limit' for r in result['recommendations'])
 cases=feasibility_test_cases()
 assert [c['before']['status'] for c in cases]==['infeasible','infeasible','blocked']
 assert all(c['verified'] for c in cases)
 assert all(not c['before']['assignments'] for c in cases)
 assert cases[1]['before']['reason']=='search_outcome'
