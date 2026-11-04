"""Validate untrusted extraction output without writing or approving rules.

Accepts every manual rule type, time rules and limit rules alike. Other
proposal kinds are rejected explicitly until their own review flows exist.
"""
from dataclasses import dataclass
from typing import Literal
from pydantic import Field, ValidationError
from app.schemas import Strict, RuleInput
import json
from app.rule_validation import rule_error


class RuleProposal(Strict):
    kind: Literal['rule']
    data: RuleInput


class ProposalEnvelope(Strict):
    decision: Literal['ready', 'clarify', 'unsupported', 'conflict', 'mixed']
    proposals: list[RuleProposal] = Field(max_length=50)
    clarifications: list[str] = Field(max_length=50)
    unsupported: list[str] = Field(max_length=50)


@dataclass(frozen=True)
class ProposalValidation:
    valid: bool
    errors: tuple[str, ...]
    eligible_for_review: bool = False
    requires_human_approval: bool = True


def validate_proposal(output, *, records, calendar):
    """records maps actual IDs to kind; calendar is the current workspace calendar.

    Syntax rejects coercion and unknown fields. Semantic checks reuse the manual
    rule validator. A valid clarify/unsupported response remains blocked from rule
    review; ready is eligibility for review only, never approval.
    """
    try:
        envelope = ProposalEnvelope.model_validate(output, strict=True)
    except ValidationError:
        return ProposalValidation(False, ('proposal_syntax',))
    errors = []
    for field in ('clarifications', 'unsupported'):
        values = getattr(envelope, field)
        if any(not v.strip() or len(v) > 500 for v in values) or len(set(values)) != len(values):
            errors.append(field + '_codes')
    p, c, u = bool(envelope.proposals), bool(envelope.clarifications), bool(envelope.unsupported)
    consistent = {
        'ready': p and not c and not u,
        'clarify': c,
        'unsupported': u and not p,
        'conflict': p and c,
        'mixed': p and (c or u),
    }[envelope.decision]
    if not consistent:
        errors.append('decision_consistency')
    signatures = set()
    for index, proposal in enumerate(envelope.proposals):
        body = proposal.data
        error = rule_error(body, records.get, calendar)
        if error:
            errors.append(f'proposals.{index}.{error}')
        signature = json.dumps({k: v for k, v in body.model_dump().items() if k != 'title'}, sort_keys=True)
        if signature in signatures:
            errors.append(f'proposals.{index}.duplicate_rule')
        signatures.add(signature)
    return ProposalValidation(not errors, tuple(errors), not errors and envelope.decision == 'ready')
