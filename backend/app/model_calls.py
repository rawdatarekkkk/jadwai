"""Explicit administrator model calls; never retain a DB lock across provider I/O."""
import asyncio
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import Field
from sqlalchemy import select
from app.dependencies import administrator, db_session, workspace_lock, lock_workspace, event, fail
from app.models import ExtractionJob
from app.schemas import Strict
from app.proposals import context
from app.provenance import fingerprint
from app.extraction import ExtractionRequest, extract_candidate
from app.extraction_completion import persist_completion
from app.openai_provider import OpenAIProvider, MODEL, PROMPT_VERSION

router=APIRouter(prefix='/api/model-calls')


def provider():
    try:return OpenAIProvider.configured()
    except ValueError:fail(503,'ai_not_configured')


class ModelInput(Strict):
    request_key: UUID
    text: str=Field(min_length=1,max_length=20000)


def job_data(row):
    return {'id':row.id,'status':row.status,'proposal_id':row.proposal_id,'model':MODEL}


@router.get('/configuration')
def configuration(user=Depends(administrator)):
    try:OpenAIProvider.configured();enabled=True
    except ValueError:enabled=False
    return {'model':MODEL,'enabled':enabled,'prompt_version':PROMPT_VERSION}


@router.get('/by-key/{key}')
def lookup(key:UUID,user=Depends(administrator),db=Depends(db_session)):
    row=db.scalar(select(ExtractionJob).where(ExtractionJob.request_key==str(key),ExtractionJob.submitted_by==user.id))
    if not row:fail(404,'not_found')
    return job_data(row)


@router.post('/{ident}/cancel')
def cancel(ident:UUID,request:Request,user=Depends(administrator),db=Depends(db_session)):
    ws=workspace_lock(db)
    row=db.get(ExtractionJob,str(ident))
    if not row or row.submitted_by!=user.id:fail(404,'not_found')
    if row.status=='cancelled':return job_data(row)
    if row.status!='running':fail(409,'invalid_transition')
    row.status='cancelled';event(db,ws,user,'model_call.cancelled',row.id);db.commit()
    return job_data(row)


@router.post('',status_code=201)
async def create(body:ModelInput,request:Request,user=Depends(administrator),db=Depends(db_session),adapter=Depends(provider)):
    actor_id=user.id
    ws=workspace_lock(db)
    digest=fingerprint({'text':body.text})
    previous=db.scalar(select(ExtractionJob).where(ExtractionJob.request_key==str(body.request_key)))
    if previous:
        if previous.submitted_by!=actor_id or previous.input_sha256!=digest:fail(409,'request_conflict')
        return job_data(previous)
    ws=lock_workspace(request,db)
    if not body.text.strip():fail(422,'invalid_input')
    # One in-flight call per administrator bounds accidental parallel spending.
    if db.scalar(select(ExtractionJob).where(ExtractionJob.submitted_by==actor_id,ExtractionJob.status=='running')):
        fail(409,'model_call_in_progress')
    original=ExtractionRequest.create(body.text,context(db,ws),ws.version,PROMPT_VERSION,'proposal-contract-v1')
    job=ExtractionJob(id=str(uuid4()),request_key=str(body.request_key),submitted_by=actor_id,input_sha256=digest,status='running')
    db.add(job);db.flush();ident=job.id
    event(db,ws,user,'model_call.started',ident)
    db.commit()  # Release account/workspace lock BEFORE awaiting network.
    try:
        result=await extract_candidate(adapter,original,timeout_seconds=25,retry_limit=0)
    except asyncio.CancelledError:
        db.rollback();workspace_lock(db)
        current=db.get(ExtractionJob,ident,populate_existing=True)
        if current.status=='running':current.status='cancelled'
        db.commit();raise
    db.expire_all()  # Refresh the pre-await identity map after concurrent writes.
    workspace_lock(db)
    job=db.get(ExtractionJob,ident,populate_existing=True)
    if job.status!='running':
        db.commit();return job_data(job)
    if result.status!='candidate':
        job.status=result.status;db.commit();return job_data(job)
    try:
        proposal=persist_completion(db,actor_id=actor_id,request_key=body.request_key,request=original,result=result)
    except HTTPException as error:
        # Persist safe terminal status; no raw provider error text is exposed.
        job.status='stale' if error.status_code==409 else 'rejected'
        db.commit()
        if error.status_code==403:raise
        return job_data(job)
    job.status='completed';job.proposal_id=proposal.id
    db.commit();return job_data(job)
