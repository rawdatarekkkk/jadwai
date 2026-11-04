"""Administrator-reviewed locks, copied from a saved validated timetable."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from app.schemas import Strict
from app.dependencies import administrator, db_session, lock_workspace, fail, event
from app.models import AssignmentLock, Record, ScheduleRun, Workspace

router=APIRouter(prefix='/api/locks')


class NewLock(Strict):
    request_key: UUID
    source_run_id: UUID
    activity_id: str
    occurrence: int = Field(ge=0,lt=10,strict=True)
    keep_instructor: bool = Field(default=False,strict=True)
    keep_time: bool = Field(default=False,strict=True)
    keep_room: bool = Field(default=False,strict=True)

    @model_validator(mode='after')
    def nonempty(self):
        if not any((self.keep_instructor,self.keep_time,self.keep_room)):raise ValueError('empty lock')
        return self


def validate_lock(row,db):
    activity=db.get(Record,row.activity_id)
    if not activity or activity.kind!='courses' or row.occurrence>=activity.data['sessions']:
        fail(422,'invalid_lock')
    data=activity.data;calendar=db.get(Workspace,1)
    if row.instructor_id is not None and row.instructor_id not in data['eligible_instructors']:
        fail(422,'invalid_lock')
    if row.room_id is not None:
        room=db.get(Record,row.room_id)
        size=sum(db.get(Record,g).data['size'] for g in data['group_ids'])
        typ='lab' if data['activity_type']=='lab' else 'lecture'
        if not room or room.kind!='rooms' or (room.data.get('capacity') or 0)<size or not set(room.data.get('room_types') or [room.data.get('room_type')]) & {typ,'flexible'} or not set(data.get('required_equipment',[]))<=set(room.data.get('equipment',[])):
            fail(422,'invalid_lock')
    if row.day is not None:
        start=row.start_minute;end=start+data['duration']
        if row.day not in calendar.days or start<calendar.start_hour*60 or end>calendar.end_hour*60:
            fail(422,'invalid_lock')
        if calendar.teaching_periods:
            if {'start':start,'end':end} not in calendar.teaching_periods:fail(422,'invalid_lock')
        elif (start-calendar.start_hour*60)%calendar.period_minutes:fail(422,'invalid_lock')


def conflicts(row,db):
    for other in db.scalars(select(AssignmentLock).where(AssignmentLock.status=='approved',AssignmentLock.activity_id==row.activity_id,AssignmentLock.id!=row.id)):
        if row.instructor_id and other.instructor_id and row.instructor_id!=other.instructor_id:
            fail(409,'lock_conflict')
        if row.occurrence==other.occurrence:
            if row.room_id and other.room_id and row.room_id!=other.room_id:fail(409,'lock_conflict')
            if row.day and other.day and (row.day,row.start_minute)!=(other.day,other.start_minute):fail(409,'lock_conflict')


@router.post('',status_code=201)
def create(body:NewLock,request:Request,user=Depends(administrator),db:DB=Depends(db_session)):
    payload=body.model_dump(mode='json',exclude={'request_key'})
    existing=db.scalar(select(AssignmentLock).where(AssignmentLock.created_by==user.id,AssignmentLock.request_key==str(body.request_key)))
    if existing:
        if existing.request_payload!=payload:fail(409,'request_conflict')
        return existing.data
    ws=lock_workspace(request,db)
    source=db.get(ScheduleRun,str(body.source_run_id))
    if not source or source.status!='completed' or not source.result or not source.result.get('validation',{}).get('passed'):
        fail(422,'invalid_lock_source')
    assignment=next((a for a in source.result['assignments'] if a['activity_id']==body.activity_id and a['occurrence']==body.occurrence),None)
    if not assignment:fail(422,'invalid_lock_source')
    row=AssignmentLock(id=str(uuid4()),source_run_id=source.id,activity_id=body.activity_id,occurrence=body.occurrence,
        instructor_id=assignment['instructor_id'] if body.keep_instructor else None,
        room_id=assignment['room_id'] if body.keep_room else None,
        day=assignment['day'] if body.keep_time else None,start_minute=assignment['start_minute'] if body.keep_time else None,
        status='draft',created_by=user.id,request_key=str(body.request_key),request_payload=payload)
    validate_lock(row,db)
    db.add(row);event(db,ws,user,'lock.created',row.id,changes_inputs=True);db.commit()
    return row.data


@router.post('/{ident}/{action}')
def transition(ident:str,action:str,request:Request,user=Depends(administrator),db:DB=Depends(db_session)):
    ws=lock_workspace(request,db);row=db.get(AssignmentLock,ident)
    if not row or action not in ('approve','revoke'):fail(404,'not_found')
    if (action=='approve')==(row.status=='approved'):fail(409,'invalid_transition')
    if action=='approve':validate_lock(row,db);conflicts(row,db)
    row.status='approved' if action=='approve' else 'draft'
    row.approved_by=user.id if action=='approve' else None
    event(db,ws,user,'lock.'+('approved' if action=='approve' else 'revoked'),row.id,changes_inputs=True)
    db.commit();return row.data


@router.delete('/{ident}',status_code=204)
def remove(ident:str,request:Request,user=Depends(administrator),db:DB=Depends(db_session)):
    ws=lock_workspace(request,db);row=db.get(AssignmentLock,ident)
    if not row:fail(404,'not_found')
    if row.status=='approved':fail(409,'revoke_before_delete')
    db.delete(row);event(db,ws,user,'lock.deleted',ident,changes_inputs=True);db.commit()
