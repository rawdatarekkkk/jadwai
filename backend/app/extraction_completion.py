"""Internal completion boundary for a future provider worker; not a public route.

Always reopen a database transaction after the provider await. This function
serializes with input/account writes and never updates existing proposal evidence.
"""
from dataclasses import asdict
import json
from uuid import UUID, uuid4
from sqlalchemy import select
from app.dependencies import workspace_lock, event, fail
from app.models import User, ExtractionProposal
from app.extraction import ExtractionRequest, ExtractionResult, parse_candidate
from app.proposals import context, validate
from app.provenance import fingerprint


def persist_completion(db, *, actor_id: str, request_key: UUID,
                       request: ExtractionRequest, result: ExtractionResult):
    """Append one validated candidate. Caller commits; never hold locks over I/O."""
    ws = workspace_lock(db)
    user = db.get(User, actor_id, populate_existing=True)
    if not user or not user.active or user.role != 'administrator':
        fail(403, 'permission_denied')
    if (result.status != 'candidate' or result.input_sha256 != request.input_sha256
            or result.input_version != request.input_version
            or result.prompt_version != request.prompt_version
            or result.schema_version != request.schema_version
            or request.schema_version != 'proposal-contract-v1'
            or not result.provider.strip() or not result.model.strip()
            or not result.attempts or result.attempts[-1].outcome != 'candidate'):
        fail(422, 'invalid_extraction_completion')
    try:
        parsed = parse_candidate(result.raw_response)
        if parsed != result.candidate_json:
            fail(422, 'invalid_extraction_completion')
        snapshot = json.loads(request.context_json)
    except (ValueError, TypeError, RecursionError):
        fail(422, 'invalid_extraction_completion')
    output = json.loads(parsed)
    payload = {'text': request.text, 'output': output}
    digest = fingerprint(payload)
    previous = db.scalar(select(ExtractionProposal).where(ExtractionProposal.request_key == str(request_key)))
    if previous:
        # A retry is a lookup of the same execution only, never a replacement.
        if (previous.submitted_by != actor_id or previous.input_sha256 != digest
                or previous.record.get('execution') != json.loads(json.dumps(asdict(result)))
                or previous.record.get('request_sha256') != request.input_sha256):
            fail(409, 'request_conflict')
        return previous
    if ws.version != request.input_version or fingerprint(context(db, ws)) != fingerprint(snapshot):
        fail(409, 'stale_proposal')
    validate(output, snapshot)
    row = ExtractionProposal(id=str(uuid4()), request_key=str(request_key), submitted_by=actor_id,
        input_version=request.input_version, input_sha256=digest,
        record={**payload, 'origin': 'provider_response',
                'model_execution_verified': False,
                'execution_kind': 'test_double' if result.provider == 'deterministic-test-double' else 'provider_transport',
                'context': snapshot, 'context_sha256': fingerprint(snapshot),
                'request_sha256': request.input_sha256, 'execution': asdict(result),
                'validator_version': 'time-rules-v1'})
    # JSON storage normalizes tuples to arrays. Normalize now for retry equality.
    row.record = json.loads(json.dumps(row.record, allow_nan=False))
    db.add(row); db.flush()
    event(db, ws, user, 'proposal.provider_completed', row.id)
    return row
