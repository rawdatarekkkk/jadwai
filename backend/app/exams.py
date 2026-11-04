from datetime import date,timedelta
from uuid import uuid4
from fastapi import APIRouter,Depends,Request
from sqlalchemy import select
from pydantic import Field,model_validator
from app.schemas import Strict
from app.models import ExamRun,CourseCatalog
from app.dependencies import administrator,db_session,lock_workspace,event
from app.exam_planning import course_inputs,generate_exam_draft,SLOTS,feasibility_test_cases

router=APIRouter(prefix='/api/exam-schedules')
class ExamInput(Strict):
    start_date: date=date(2026,10,20)
    end_date: date=date(2026,10,31)
    exclude_fridays: bool=True
    max_exams_per_cohort_day: int=Field(default=1,ge=1,le=3,strict=True)
    @model_validator(mode='after')
    def valid_period(self):
        if not 0<=(self.end_date-self.start_date).days<=60:raise ValueError('Exam period must be between 1 and 61 days')
        return self

def representation(row):return dict(id=row.id,input_version=row.input_version,created_at=row.created_at,snapshot=row.snapshot,result=row.result)
@router.get('')
def list_exams(user=Depends(administrator),db=Depends(db_session)):
    return [representation(r) for r in db.scalars(select(ExamRun).order_by(ExamRun.created_at.desc()).limit(20))]
@router.post('',status_code=201)
def create_exam(body:ExamInput,request:Request,user=Depends(administrator),db=Depends(db_session)):
    ws=lock_workspace(request,db)
    courses,missing=course_inputs(db.scalars(select(CourseCatalog).order_by(CourseCatalog.code)).all())
    days=[body.start_date+timedelta(days=i) for i in range((body.end_date-body.start_date).days+1)]
    snapshot={'courses':courses,'missing_cohort_codes':missing,'dates':[d.isoformat() for d in days if not body.exclude_fridays or d.weekday()!=4],'slots':SLOTS,'max_exams_per_cohort_day':body.max_exams_per_cohort_day,'timezone':ws.timezone,'settings':body.model_dump(mode='json')}
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
    writer.writerow(['Date','Start','End','Course code','Course name','Programs','Status'])
    for a in row.result['assignments']:
        writer.writerow([safe(v) for v in [a['date'],a['start_time'],a['end_time'],a['course_code'],a['course_name'],'; '.join(f'{p["program_or_cohort"]} / semester {p["semester"] or "unknown"}' for p in a['programs']),'Draft: dates and times only']])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="JadwAI-midterms-{row.snapshot["settings"]["start_date"]}.csv"'})
