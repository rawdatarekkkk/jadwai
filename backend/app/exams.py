from datetime import date,timedelta
from uuid import uuid4
from fastapi import APIRouter,Depends,Request
from sqlalchemy import select
from pydantic import Field,model_validator
from app.schemas import Strict
from app.models import ExamRun,CourseCatalog,Record,Rule,Workspace
from app.dependencies import administrator,db_session,lock_workspace,event
from app.exam_planning import course_inputs,generate_exam_draft,SLOTS,feasibility_test_cases,DEFAULT_COHORT_RULES

router=APIRouter(prefix='/api/exam-schedules')
class ExamInput(Strict):
    start_date: date=date(2026,10,20)
    end_date: date=date(2026,10,31)
    exclude_fridays: bool=True
    max_exams_per_cohort_day: int=Field(default=1,ge=1,le=3,strict=True)
    use_halls: bool=True
    assign_invigilators: bool=True
    time_limit_seconds: int=Field(default=20,ge=1,le=300,strict=True)
    @model_validator(mode='after')
    def valid_period(self):
        if not 0<=(self.end_date-self.start_date).days<=60:raise ValueError('Exam period must be between 1 and 61 days')
        return self

def representation(row):return dict(id=row.id,input_version=row.input_version,created_at=row.created_at,snapshot=row.snapshot,result=row.result,name=row.name,published_at=row.published_at)
@router.get('')
def list_exams(user=Depends(administrator),db=Depends(db_session)):
    return [representation(r) for r in db.scalars(select(ExamRun).order_by(ExamRun.created_at.desc()).limit(20))]
@router.post('',status_code=201)
def create_exam(body:ExamInput,request:Request,user=Depends(administrator),db=Depends(db_session)):
    ws=lock_workspace(request,db)
    records=db.scalars(select(Record)).all()
    sizes={r.id:r.data['size'] for r in records if r.kind=='groups'}
    courses,missing=course_inputs(db.scalars(select(CourseCatalog).order_by(CourseCatalog.code)).all(),ws.exam_cohort_rules or DEFAULT_COHORT_RULES,sizes)
    # Advising students sit the exams of their own courses: each is a cohort of their own.
    from app.advising import student_rows
    for student in student_rows(db):
        added={c['course_id'] for c in student['changes'] if c['action']=='add'}
        for row in courses:
            if row['id'] in student['course_ids']:
                row['participants']=sorted(set(row['participants'])|{'student:'+student['code']})
                if row['id'] in added and row['students']:row['students']+=1
    days=[body.start_date+timedelta(days=i) for i in range((body.end_date-body.start_date).days+1)]
    snapshot={'courses':courses,'missing_cohort_codes':missing,'dates':[d.isoformat() for d in days if not body.exclude_fridays or d.weekday()!=4],'slots':SLOTS,'max_exams_per_cohort_day':body.max_exams_per_cohort_day,'timezone':ws.timezone,'settings':body.model_dump(mode='json'),'time_limit_seconds':body.time_limit_seconds}
    if body.use_halls:
        snapshot['halls']=[{'id':r.id,'code':r.code,'name':r.name,'capacity':r.data['capacity']} for r in sorted(records,key=lambda r:r.code) if r.kind=='rooms' and 'exam_hall' in (r.data.get('room_types') or []) and r.data.get('capacity')]
        if body.assign_invigilators:
            rules=[r.data for r in db.scalars(select(Rule).where(Rule.status=='approved',Rule.type=='unavailable'))]
            snapshot['invigilators']=[{'id':r.id,'code':r.code,'name':r.name,'day_off':r.data.get('day_off'),'unavailable':[x for x in rules if x['instructor_id']==r.id]} for r in sorted(records,key=lambda r:r.code) if r.kind=='instructors' and r.data.get('position')=='ta']
    row=ExamRun(id=str(uuid4()),input_version=ws.version,snapshot=snapshot,result=generate_exam_draft(snapshot))
    db.add(row);event(db,ws,user,'exam.generated',f'{len(courses)} course exams: {row.result["status"]}')
    db.commit();return representation(row)

@router.post('/feasibility-tests')
def test_feasibility(user=Depends(administrator)):
    return feasibility_test_cases()

@router.get('/{ident}/export')
def export_exam(ident:str,user=Depends(administrator),db=Depends(db_session)):
    import csv,io
    from fastapi import Response
    from app.dependencies import fail
    row=db.get(ExamRun,ident)
    if not row:fail(404,'not_found')
    if row.result['status']!='completed':fail(409,'invalid_transition')
    stream=io.StringIO();writer=csv.writer(stream)
    def safe(value):
        value=str(value)
        return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value
    writer.writerow(['Date','Start','End','Course code','Course name','Programs','Students','Halls','Invigilators','Status'])
    for a in row.result['assignments']:
        halls=a.get('halls')
        status='Published' if row.published_at else 'Draft' if halls is not None else 'Draft: dates and times only'
        writer.writerow([safe(v) for v in [a['date'],a['start_time'],a['end_time'],a['course_code'],a['course_name'],'; '.join(f'{p["program_or_cohort"]} / semester {p["semester"] or "unknown"}' for p in a['programs']),a.get('students') or '','; '.join(h['room_code'] for h in halls or []),'; '.join(h.get('invigilator_name') or '' for h in halls or []),status]])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="JadwAI-midterms-{row.snapshot["settings"]["start_date"]}.csv"'})


class CohortRules(Strict):
    broad_programs: list[str]=Field(max_length=100)
    tracks: dict[str,list[str]]
    aliases: dict[str,str]


@router.get('/cohort-rules')
def cohort_rules(user=Depends(administrator),db=Depends(db_session)):
    return db.get(Workspace,1).exam_cohort_rules or DEFAULT_COHORT_RULES


@router.put('/cohort-rules')
def save_cohort_rules(body:CohortRules,request:Request,user=Depends(administrator),db=Depends(db_session)):
    import re
    clean=lambda value:re.sub(r'[^a-z0-9]','',value.lower())
    ws=lock_workspace(request,db)
    ws.exam_cohort_rules={'broad_programs':sorted({clean(p) for p in body.broad_programs if clean(p)}),
        'tracks':{faculty.strip().upper():[clean(t) for t in tracks if clean(t)] for faculty,tracks in body.tracks.items()},
        'aliases':{clean(k):clean(v) for k,v in body.aliases.items() if clean(k) and clean(v)}}
    event(db,ws,user,'exam.cohort_rules_updated',changes_inputs=True)
    db.commit();return ws.exam_cohort_rules
