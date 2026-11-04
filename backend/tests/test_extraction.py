import asyncio
import json
import pytest
from app.extraction import ExtractionRequest, DeterministicProvider, RetryableProviderError, extract_candidate


def request():
    return ExtractionRequest.create('لا محاضرات يوم السبت', {'days': ['Saturday']}, 23, 'draft-v1', 'proposal-contract-v1')


def run(provider, **kwargs):
    return asyncio.run(extract_candidate(provider, request(), **kwargs))


def test_candidate_is_unapproved_and_bound_to_snapshot():
    context = {'days': ['Saturday']}
    req = ExtractionRequest.create('Saturday', context, 23, 'v1', 'v1')
    original = req.input_sha256
    context['days'].clear()
    assert req.input_sha256 == original
    result = asyncio.run(extract_candidate(DeterministicProvider('{"decision":"ready"}'), req))
    assert result.status == 'candidate'
    assert result.requires_validation and result.requires_human_approval
    assert result.input_version == 23 and result.input_sha256 == original
    assert json.loads(result.candidate_json) == {'decision': 'ready'}
    assert result.attempts[0].latency_ms >= 0
    assert ExtractionRequest.create('Sunday', {}, 23, 'v1', 'v1').input_sha256 != original


@pytest.mark.parametrize('response', ['[]', '```json\n{}\n```', '{"a":1,"a":2}', '{"a":NaN}', '{"a":', None])
def test_invalid_response_is_not_repaired_or_retried(response):
    result = run(DeterministicProvider(response), retry_limit=3)
    assert result.status == 'invalid_response'
    assert result.candidate_json is None and len(result.attempts) == 1


def test_transient_failure_retries_with_same_input():
    class Provider(DeterministicProvider):
        calls = 0
        async def extract(self, req):
            self.calls += 1
            if self.calls == 1:
                raise RetryableProviderError('secret must not leak')
            return self.response
    result = run(Provider('{}'), retry_limit=1)
    assert [a.outcome for a in result.attempts] == ['provider_unavailable', 'candidate']
    assert 'secret' not in repr(result)


def test_timeout_is_bounded_and_does_not_produce_candidate():
    class Slow(DeterministicProvider):
        async def extract(self, req):
            await asyncio.sleep(1)
            return '{}'
    result = run(Slow('{}'), timeout_seconds=.001, retry_limit=1)
    assert result.status == 'timeout' and len(result.attempts) == 2
    assert result.candidate_json is None


def test_permanent_error_is_not_retried_or_exposed():
    class Broken(DeterministicProvider):
        async def extract(self, req):
            raise RuntimeError('private API key')
    result = run(Broken('{}'), retry_limit=3)
    assert result.status == 'provider_error' and len(result.attempts) == 1
    assert 'private API key' not in repr(result)


def test_caller_cancellation_propagates():
    class Cancelled(DeterministicProvider):
        async def extract(self, req):
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        run(Cancelled('{}'))


@pytest.mark.parametrize('options', [{'retry_limit': True}, {'retry_limit': 4}, {'timeout_seconds': float('nan')}, {'timeout_seconds': 0}])
def test_invalid_execution_policy_rejected(options):
    with pytest.raises(ValueError):
        run(DeterministicProvider('{}'), **options)
