"""Administrator research workspace; no gold, reserved content or provider calls."""
import json,sys,hashlib
from pathlib import Path
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,Response
from pydantic import Field
from sqlalchemy import select
from app.schemas import Strict,Name
from app.dependencies import administrator,db_session,workspace_lock,event,fail
from app.models import EvaluationReview,EvaluationAdjudication

PROJECT=Path(__file__).resolve().parents[2]
if str(PROJECT) not in sys.path:sys.path.insert(0,str(PROJECT))
from evaluation.development import load_bundle,review_pack,import_review
from evaluation.runner import digest
BUNDLE=PROJECT/'evaluation'/'development-v2'
GUIDE=PROJECT/'evaluation'/'guides'/'annotation-guide-v2.md'
PROTOCOL=PROJECT/'evaluation'/'protocols'/'admin-review-v1.md'
router=APIRouter(prefix='/api/evaluation')

def pack():return review_pack(BUNDLE,6,42)
def evidence(row):return {'id':row.id,'reviewer_id':row.reviewer_id,'created_at':row.created_at,'items':len(row.record['annotations']),'manifest_sha256':row.record['manifest_sha256'],'adjudicated':False,'identity_verification':'operator_declared_only'}

@router.get('')
def summary(user=Depends(administrator),db=Depends(db_session)):
    try:manifest,contexts,rows=load_bundle(BUNDLE)
    except (ValueError,KeyError,OSError):fail(503,'evaluation_bundle_unavailable')
    return {'phase':5,'status':'development_pending_admin_review','review_protocol':'single_admin_reviewer','independent_review_claim':False,'dataset_version':manifest['dataset_version'],'counts':manifest['counts'],'languages':['en','ar','arz','mixed'],'guide_version':manifest['guide_version'],'review_pack_items':24,'reviews':[evidence(r) for r in db.scalars(select(EvaluationReview).order_by(EvaluationReview.created_at.desc()))],'adjudications':[adjudication_evidence(r) for r in db.scalars(select(EvaluationAdjudication).order_by(EvaluationAdjudication.created_at.desc()))],'model_calls':0,'independently_adjudicated':False,'reserved_is_blind':False}

@router.get('/review-pack')
def download_pack(user=Depends(administrator)):
    try:content=json.dumps(pack(),ensure_ascii=False,indent=2)
    except (ValueError,KeyError,OSError):fail(503,'evaluation_bundle_unavailable')
    return Response(content,media_type='application/json',headers={'Content-Disposition':'attachment; filename="JadwAI-annotation-review-pack-v2.json"'})

@router.get('/guide')
def guide(user=Depends(administrator)):
    try:load_bundle(BUNDLE);text=GUIDE.read_text()
    except (ValueError,KeyError,OSError):fail(503,'evaluation_bundle_unavailable')
    return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="JadwAI-annotation-guide-v2.md"'})

@router.get('/protocol')
def protocol(user=Depends(administrator)):
    try:text=PROTOCOL.read_text()
    except OSError:fail(503,'evaluation_protocol_unavailable')
    return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="JadwAI-admin-review-protocol-v1.md"'})

class ReviewInput(Strict):
    request_key: UUID
    reviewer_id: Name
    annotated: dict=Field()

@router.post('/reviews',status_code=201)
def save_review(body:ReviewInput,user=Depends(administrator),db=Depends(db_session)):
    try:
        content=json.dumps(body.annotated,ensure_ascii=False,allow_nan=False)
        if len(content.encode())>2_000_000:fail(413,'review_too_large')
        fingerprint=digest({'reviewer_id':body.reviewer_id,'annotated':body.annotated})
    except (ValueError,TypeError):fail(422,'invalid_review')
    ws=workspace_lock(db)
    prior=db.scalar(select(EvaluationReview).where(EvaluationReview.request_key==str(body.request_key)))
    if prior:
        if prior.submitted_by!=user.id or prior.input_sha256!=fingerprint:fail(409,'review_request_conflict')
        return evidence(prior)
    try:
        record=import_review(BUNDLE,pack(),body.annotated,body.reviewer_id)
        record['review_protocol']='single-admin-review-v1'
        record['reviewer_role']='administrator'
        record['review_protocol_sha256']=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    except (ValueError,KeyError,TypeError,IndexError):fail(422,'invalid_review')
    except OSError:fail(503,'evaluation_bundle_unavailable')
    row=EvaluationReview(id=str(uuid4()),request_key=str(body.request_key),submitted_by=user.id,reviewer_id=body.reviewer_id,input_sha256=fingerprint,record=record)
    db.add(row);db.flush();event(db,ws,user,'evaluation.review_submitted',f'{body.reviewer_id}: {len(record["annotations"])} annotations',changes_inputs=False)
    db.commit();return evidence(row)

@router.get('/reviews/{ident}/export')
def export_review(ident:str,user=Depends(administrator),db=Depends(db_session)):
    row=db.get(EvaluationReview,ident)
    if not row:fail(404,'not_found')
    return Response(json.dumps(row.record,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="JadwAI-review-{row.id}.json"'})

@router.get('/compare')
def compare_saved_reviews(first:UUID,second:UUID,download:bool=False,user=Depends(administrator),db=Depends(db_session)):
    from evaluation.development import compare_reviews
    if first==second:fail(422,'distinct_reviews_required')
    left=db.get(EvaluationReview,str(first));right=db.get(EvaluationReview,str(second))
    if not left or not right:fail(404,'not_found')
    try:report=compare_reviews(left.record,right.record)
    except (ValueError,KeyError,TypeError):fail(422,'incompatible_reviews')
    try:manifest,contexts,rows=load_bundle(BUNDLE)
    except (ValueError,KeyError,OSError):fail(503,'evaluation_bundle_unavailable')
    if report['manifest_sha256']!=digest(manifest):fail(409,'review_bundle_version_unavailable')
    by_id={r['id']:r for r in rows};a={r['id']:r for r in left.record['annotations']};b={r['id']:r for r in right.record['annotations']}
    details=[]
    for ident in report['semantic_agreement']['disagreement_ids']:
        source=by_id.get(ident)
        if source is None:fail(409,'review_bundle_version_unavailable')
        details.append({'id':ident,'text':source['text'],'language':source['language'],'context_id':source['context_id'],'first_annotation':a[ident]['annotation'],'first_rationale':a[ident]['rationale'],'second_annotation':b[ident]['annotation'],'second_rationale':b[ident]['rationale']})
    result={**report,'review_ids':[left.id,right.id],'disagreements':details,'contexts':[contexts[k] for k in sorted({d['context_id'] for d in details})],'gold_included':False}
    if download:return Response(json.dumps(result,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="JadwAI-comparison-{left.id[:8]}-{right.id[:8]}.json"'})
    return result


def adjudication_evidence(row):
    return {'id':row.id,'adjudicator_id':row.adjudicator_id,'first_review_id':row.first_review_id,'second_review_id':row.second_review_id,'created_at':row.created_at,'items':len(row.record['decisions']),'release_promoted':False}

class ResolutionInput(Strict):
    id: Name
    annotation: dict
    rationale: str=Field(min_length=1,max_length=4000)

class AdjudicationInput(Strict):
    request_key: UUID
    first_review_id: UUID
    second_review_id: UUID
    adjudicator_id: Name
    resolutions: list[ResolutionInput]=Field(max_length=24)

@router.post('/adjudications',status_code=201)
def save_adjudication(body:AdjudicationInput,user=Depends(administrator),db=Depends(db_session)):
    from evaluation.development import adjudicate
    try:
        value=body.model_dump(mode='json');serialized=json.dumps(value,allow_nan=False)
        if len(serialized.encode())>2_000_000:fail(413,'adjudication_too_large')
        fingerprint=digest(value)
    except (ValueError,TypeError):fail(422,'invalid_adjudication')
    ws=workspace_lock(db)
    prior=db.scalar(select(EvaluationAdjudication).where(EvaluationAdjudication.request_key==str(body.request_key)))
    if prior:
        if prior.submitted_by!=user.id or prior.input_sha256!=fingerprint:fail(409,'adjudication_request_conflict')
        return adjudication_evidence(prior)
    left=db.get(EvaluationReview,str(body.first_review_id));right=db.get(EvaluationReview,str(body.second_review_id))
    if not left or not right:fail(404,'not_found')
    if body.adjudicator_id.casefold() in {left.reviewer_id.casefold(),right.reviewer_id.casefold()}:fail(422,'distinct_adjudicator_required')
    try:record=adjudicate(BUNDLE,left.record,right.record,[r.model_dump() for r in body.resolutions],body.adjudicator_id)
    except (ValueError,KeyError,TypeError,IndexError):fail(422,'invalid_adjudication')
    except OSError:fail(503,'evaluation_bundle_unavailable')
    row=EvaluationAdjudication(id=str(uuid4()),request_key=str(body.request_key),submitted_by=user.id,first_review_id=left.id,second_review_id=right.id,adjudicator_id=body.adjudicator_id,input_sha256=fingerprint,record=record)
    db.add(row);db.flush();event(db,ws,user,'evaluation.adjudication_recorded',f'{body.adjudicator_id}: {len(body.resolutions)} disputed annotations',changes_inputs=False)
    db.commit();return adjudication_evidence(row)

@router.get('/adjudications/{ident}/export')
def export_adjudication(ident:str,user=Depends(administrator),db=Depends(db_session)):
    row=db.get(EvaluationAdjudication,ident)
    if not row:fail(404,'not_found')
    return Response(json.dumps(row.record,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="JadwAI-adjudication-{row.id}.json"'})
