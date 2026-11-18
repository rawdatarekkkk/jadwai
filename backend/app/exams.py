from datetime import date,timedelta
from uuid import uuid4
from fastapi import APIRouter,Depends,Request
from sqlalchemy import select
from typing import Annotated,Literal
from pydantic import StringConstraints
import re
from pydantic import Field,model_validator
from app.schemas import Strict
from app.models import ExamRun,CourseCatalog,Record,Rule,Workspace
from app.dependencies import administrator,db_session,lock_workspace,event
from app.exam_planning import course_inputs,generate_exam_draft,SLOTS,EXAM_TYPES,DEFAULT_STARTS,feasibility_test_cases,DEFAULT_COHORT_RULES,minutes

router=APIRouter(prefix='/api/exam-schedules')
TIME=r'^([01]\d|2[0-3]):[0-5]\d$'
StartTime=Annotated[str,StringConstraints(pattern=TIME)]
LABELS={'quiz':'Quiz','midterm':'Midterm','makeup':'Second-chance midterm','final':'Final'}


class ExamInput(Strict):
    """One exam timetable: a quiz round, the midterms, or the finals (with second-chance midterms)."""
    course_ids: list[str] | None = Field(default=None, min_length=1, max_length=2000)
    start_date: date=date(2026,10,20)
    end_date: date=date(2026,10,31)
    exclude_fridays: bool=True
    max_exams_per_cohort_day: int=Field(default=1,ge=1,le=6,strict=True)
    kind: Literal['quiz','midterm','final']='midterm'
    quiz_number: int=Field(default=1,ge=1,le=10,strict=True)
    quiz_minutes: int=Field(default=30,ge=15,le=60,multiple_of=15,strict=True)
    # Start times per exam type; omitted types use DEFAULT_STARTS.
    starts: dict[Literal['quiz','midterm','makeup','final'],list[StartTime]]=Field(default_factory=dict)
    # Exams left out of this timetable, as "<course id>:<type>".
    skip: list[str]=Field(default_factory=list,max_length=5000)
    # Students expected at a course's second-chance midterm (default: 10% of the course, at least 1).
    makeup_students: dict[str,int]=Field(default_factory=dict,max_length=2000)
    use_halls: bool=True
    assign_invigilators: bool=True
    time_limit_seconds: int=Field(default=20,ge=1,le=300,strict=True)
    @model_validator(mode='after')
    def valid_period(self):
        if not 0<=(self.end_date-self.start_date).days<=60:raise ValueError('Exam period must be between 1 and 61 days')
        if any(not 1<=n<=5000 for n in self.makeup_students.values()):raise ValueError('Invalid student count')
        if any(len(v)>12 or len(set(v))!=len(v) for v in self.starts.values()):raise ValueError('Invalid start times')
        return self

    def start_times(self):
        types={'quiz':['quiz'],'midterm':['midterm'],'final':['final','makeup']}[self.kind]
        return {t:sorted(self.starts.get(t) or DEFAULT_STARTS[t]) for t in types}


def exam_items(body,courses):
    """The exams of this timetable, one row each, from every course's exam plan."""
    items=[]
    def add(row,kind,minutes,label,students=None):
        key=f"{row['id']}:{kind}" if kind!='quiz' else f"{row['id']}:quiz{body.quiz_number}"
        if f"{row['id']}:{kind}" in body.skip or key in body.skip:return
        items.append({**row,'id':key,'course_id':row['id'],'exam_type':kind,'duration_minutes':minutes,'label':label,
                      'students':students if students is not None else row['students']})
    for row in courses:
        if body.kind=='quiz' and row.get('quiz_count',3)>=body.quiz_number:
            add(row,'quiz',body.quiz_minutes,f'Quiz {body.quiz_number}')
        elif body.kind=='midterm':
            add(row,'midterm',120,'Midterm')
        elif body.kind=='final':
            add(row,'final',180,'Final')
            if row.get('second_chance',True):
                expected=body.makeup_students.get(row['id']) or (max(1,-(-row['students']//10)) if row['students'] else None)
                add(row,'makeup',120,'Second-chance midterm',expected)
    return items


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
    starts=body.start_times()
    if body.kind=='final':
        # The first slot is reserved for second-chance midterms: no final may overlap it.
        from app.dependencies import fail
        windows=[(minutes(t),minutes(t)+120) for t in starts['makeup']]
        if any(minutes(f)<b and a<minutes(f)+180 for f in starts['final'] for a,b in windows):fail(422,'final_overlaps_second_chance')
    if body.course_ids is not None:
        from app.dependencies import fail
        wanted=set(body.course_ids)
        if len(wanted)!=len(body.course_ids) or wanted-{course['id'] for course in courses}:
            fail(422,'invalid_exam_scope')
        courses=[course for course in courses if course['id'] in wanted]
    courses=exam_items(body,courses)
    missing=sorted({c['code'] for c in courses if c['code'] in missing})
    days=[body.start_date+timedelta(days=i) for i in range((body.end_date-body.start_date).days+1)]
    snapshot={'courses':courses,'missing_cohort_codes':missing,'dates':[d.isoformat() for d in days if not body.exclude_fridays or d.weekday()!=4],'starts':starts,'max_exams_per_cohort_day':body.max_exams_per_cohort_day,'timezone':ws.timezone,'settings':body.model_dump(mode='json'),'time_limit_seconds':body.time_limit_seconds}
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
    writer.writerow(['Date','Start','End','Type','Minutes','Course code','Course name','Programs','Students','Halls','Invigilators','Status'])
    for a in row.result['assignments']:
        halls=a.get('halls')
        status='Published' if row.published_at else 'Draft' if halls is not None else 'Draft: dates and times only'
        writer.writerow([safe(v) for v in [a['date'],a['start_time'],a['end_time'],a.get('exam_type','midterm'),a.get('duration_minutes',120),a['course_code'],a['course_name'],'; '.join(f'{p["program_or_cohort"]} / semester {p["semester"] or "unknown"}' for p in a['programs']),a.get('students') or '','; '.join(h['room_code'] for h in halls or []),'; '.join(h.get('invigilator_name') or '' for h in halls or []),status]])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="JadwAI-midterms-{row.snapshot["settings"]["start_date"]}.csv"'})


@router.get('/{ident}/exams.pdf')
def exam_timetable_pdf(ident:str,q:str='',user=Depends(administrator),db=Depends(db_session)):
    """Landscape PDF of the exam timetable (optionally only exams matching the page's search)."""
    from urllib.parse import quote
    from fastapi import Response
    from app.dependencies import fail
    from app.exam_pdf import exam_pdf
    from app.models import Workspace
    row=db.get(ExamRun,ident)
    if not row:fail(404,'not_found')
    if row.result['status']!='completed':fail(409,'invalid_transition')
    content,name=exam_pdf(row,q[:100],published=bool(row.published_at),stale=row.input_version!=db.get(Workspace,1).version)
    fallback=name.encode('ascii','ignore').decode('ascii') or 'Exam Schedule'
    return Response(content,media_type='application/pdf',headers={'Content-Disposition':f"attachment; filename=\"{fallback}.pdf\"; filename*=UTF-8''{quote(name+'.pdf',safe='')}"})


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


@router.get('/{ident}')
def get_exam_schedule(ident: str, user=Depends(administrator), db=Depends(db_session)):
    from app.dependencies import fail
    row=db.get(ExamRun,ident)
    if not row:fail(404,'not_found')
    return representation(row)
