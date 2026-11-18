"""Admin-only imported candidate review. No provider calls or automatic approval."""
import json
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select
from app.dependencies import administrator, db_session, lock_workspace, workspace_lock, event, fail
from app.models import ExtractionProposal, ExtractionProposalReview, Record, Rule
from app.schemas import Strict
from app.provenance import fingerprint
from app.proposal_validation import validate_proposal, ProposalEnvelope

router = APIRouter(prefix='/api/proposals')


class ImportedProposal(Strict):
    request_key: UUID
    text: str = Field(min_length=1, max_length=20000)
    output: dict


class ReviewProposal(Strict):
    request_key: UUID
    action: Literal['dismiss', 'create_drafts']
    rationale: str = Field(min_length=1, max_length=2000)
    corrected_output: dict | None = None


def context(db, ws):
    rows = db.scalars(select(Record).order_by(Record.id)).all()
    return {'records': [{'id': r.id, 'kind': r.kind, 'data': r.data} for r in rows],
            'calendar': {'days': ws.days, 'start_hour': ws.start_hour, 'end_hour': ws.end_hour, 'period_minutes': ws.period_minutes, 'teaching_periods': ws.teaching_periods, 'timezone': ws.timezone}}


def submitted_fingerprint(payload):
    try:
        serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        fail(422, 'invalid_proposal')
    if len(serialized.encode()) > 1000000:
        fail(413, 'proposal_too_large')
    return fingerprint(payload)


def validate(output, snapshot):
    submitted_fingerprint(output)
    result = validate_proposal(output, records={r['id']: r['kind'] for r in snapshot['records']}, calendar=snapshot['calendar'])
    if not result.valid:
        fail(422, 'invalid_proposal')
    return result


def data(row, db, version):
    review = db.scalar(select(ExtractionProposalReview).where(ExtractionProposalReview.proposal_id == row.id))
    return {'id': row.id, 'input_version': row.input_version, 'input_sha256': row.input_sha256,
            'created_at': row.created_at, 'record': row.record,
            'stale': row.input_version != version,
            'review': {'id': review.id, 'record': review.record} if review else None}


@router.get('')
def listing(user=Depends(administrator), db=Depends(db_session)):
    ws = workspace_lock(db, read=True)
    rows = db.scalars(select(ExtractionProposal).order_by(ExtractionProposal.created_at.desc()).limit(100)).all()
    return {'version': ws.version, 'proposals': [data(r, db, ws.version) for r in rows]}


@router.post('', status_code=201)
def submit(body: ImportedProposal, request: Request, user=Depends(administrator), db=Depends(db_session)):
    payload = body.model_dump(mode='json', exclude={'request_key'})
    digest = submitted_fingerprint(payload)
    ws = workspace_lock(db)
    previous = db.scalar(select(ExtractionProposal).where(ExtractionProposal.request_key == str(body.request_key)))
    if previous:
        if previous.submitted_by != user.id or previous.input_sha256 != digest:
            fail(409, 'request_conflict')
        return data(previous, db, ws.version)
    ws = lock_workspace(request, db)
    if not body.text.strip():
        fail(422, 'invalid_input')
    snapshot = context(db, ws)
    validate(body.output, snapshot)
    row = ExtractionProposal(id=str(uuid4()), request_key=str(body.request_key), submitted_by=user.id,
        input_version=ws.version, input_sha256=digest,
        record={**payload, 'origin': 'administrator_import', 'model_execution_verified': False,
                'context': snapshot, 'context_sha256': fingerprint(snapshot), 'validator_version': 'rules-v2'})
    db.add(row); db.flush()
    event(db, ws, user, 'proposal.imported', row.id)
    db.commit()
    return data(row, db, ws.version)


@router.post('/{ident}/review', status_code=201)
def review(ident: UUID, body: ReviewProposal, request: Request, user=Depends(administrator), db=Depends(db_session)):
    payload = body.model_dump(mode='json', exclude={'request_key'})
    digest = submitted_fingerprint({'proposal_id': str(ident), **payload})
    ws = workspace_lock(db)
    previous = db.scalar(select(ExtractionProposalReview).where(ExtractionProposalReview.request_key == str(body.request_key)))
    if previous:
        if previous.submitted_by != user.id or previous.input_sha256 != digest:
            fail(409, 'request_conflict')
        return {'id': previous.id, **previous.record, 'version': ws.version}
    row = db.get(ExtractionProposal, str(ident))
    if not row:
        fail(404, 'not_found')
    if db.scalar(select(ExtractionProposalReview).where(ExtractionProposalReview.proposal_id == row.id)):
        fail(409, 'proposal_already_reviewed')
    ws = lock_workspace(request, db)
    if not body.rationale.strip():
        fail(422, 'invalid_input')
    rule_ids = []
    if body.action == 'create_drafts':
        snapshot = context(db, ws)
        if row.input_version != ws.version or row.record['context_sha256'] != fingerprint(snapshot):
            fail(409, 'stale_proposal')
        output = body.corrected_output if body.corrected_output is not None else row.record['output']
        if not validate(output, snapshot).eligible_for_review:
            fail(422, 'proposal_requires_clarification')
        for proposal in ProposalEnvelope.model_validate(output, strict=True).proposals:
            rule = Rule(id=str(uuid4()), data=proposal.data.model_dump(), status='draft')
            db.add(rule); rule_ids.append(rule.id)
    elif body.corrected_output is not None:
        fail(422, 'unexpected_correction')
    record = {**payload, 'rule_ids': rule_ids, 'rules_approved': False, 'source_sha256': row.input_sha256}
    result = ExtractionProposalReview(id=str(uuid4()), proposal_id=row.id, request_key=str(body.request_key),
        submitted_by=user.id, input_sha256=digest, record=record)
    db.add(result)
    event(db, ws, user, 'proposal.' + body.action, row.id, changes_inputs=bool(rule_ids))
    db.commit()
    return {'id': result.id, **record, 'version': ws.version}


class TypedConstraint(Strict):
    request_key: UUID
    text: str = Field(min_length=1, max_length=2000)


@router.post('/interpret', status_code=201)
def interpret(body: TypedConstraint, request: Request, user=Depends(administrator), db=Depends(db_session)):
    """Run the built-in parser and keep its interpretation for review like any proposal."""
    from app.rule_parser import parse
    payload = body.model_dump(mode='json', exclude={'request_key'})
    digest = submitted_fingerprint(payload)
    ws = workspace_lock(db)
    previous = db.scalar(select(ExtractionProposal).where(ExtractionProposal.request_key == str(body.request_key)))
    if previous:
        if previous.submitted_by != user.id or previous.input_sha256 != digest:
            fail(409, 'request_conflict')
        return data(previous, db, ws.version)
    ws = lock_workspace(request, db)
    if not body.text.strip():
        fail(422, 'invalid_input')
    snapshot = context(db, ws)
    output = parse(body.text, snapshot)
    check = validate_proposal(output, records={r['id']: r['kind'] for r in snapshot['records']}, calendar=snapshot['calendar'])
    if not check.valid:
        # Never store an invalid interpretation as if it were reviewable.
        output = {'decision': 'clarify', 'proposals': [], 'clarifications': sorted({e.split('.')[-1] for e in check.errors}), 'unsupported': []}
    row = ExtractionProposal(id=str(uuid4()), request_key=str(body.request_key), submitted_by=user.id,
        input_version=ws.version, input_sha256=digest,
        record={**payload, 'output': output, 'origin': 'builtin_parser', 'interpreter': 'builtin-parser-v1',
                'model_execution_verified': True, 'context': snapshot, 'context_sha256': fingerprint(snapshot), 'validator_version': 'rules-v2'})
    db.add(row); db.flush()
    event(db, ws, user, 'proposal.interpreted', row.id)
    db.commit()
    return data(row, db, ws.version)
