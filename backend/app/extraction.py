"""Provider-independent extraction transport. No database writes or rule approval.

A successful response is only a candidate JSON object. Schema, entity and review
validation are required by the eventual proposal workflow before use.
"""
import asyncio
import hashlib
import json
import math
import time
from dataclasses import dataclass
from typing import Protocol


class ProviderRefusal(Exception):
    pass


class IncompleteResponse(Exception):
    pass


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class RetryableProviderError(Exception):
    """Temporary provider failure; its message is never copied to results."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class ExtractionRequest:
    text: str
    context_json: str
    input_version: int
    prompt_version: str
    schema_version: str

    @classmethod
    def create(cls, text, context, input_version, prompt_version, schema_version):
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            raise ValueError('Nonempty input text of at most 20000 characters required')
        if not isinstance(context, dict) or type(input_version) is not int or input_version < 0:
            raise ValueError('Context and nonnegative input version required')
        if any(not isinstance(v, str) or not v.strip() for v in (prompt_version, schema_version)):
            raise ValueError('Prompt and schema versions required')
        serialized = canonical(context)
        if len(serialized.encode()) > 1000000:
            raise ValueError('Context exceeds size limit')
        return cls(text, serialized, input_version, prompt_version, schema_version)

    @property
    def input_sha256(self):
        return hashlib.sha256(canonical(self.__dict__).encode()).hexdigest()


class ExtractionProvider(Protocol):
    name: str
    model: str

    async def extract(self, request: ExtractionRequest) -> str | ProviderResponse:
        """Return raw JSON text, or raise a provider error."""


@dataclass(frozen=True)
class Attempt:
    number: int
    outcome: str
    latency_ms: float


@dataclass(frozen=True)
class ExtractionResult:
    status: str
    provider: str
    model: str
    input_sha256: str
    input_version: int
    prompt_version: str
    schema_version: str
    attempts: tuple[Attempt, ...]
    raw_response: str | None = None
    candidate_json: str | None = None
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    requires_validation: bool = True
    requires_human_approval: bool = True


def parse_candidate(raw):
    if not isinstance(raw, str) or len(raw.encode()) > 1000000:
        raise ValueError('Invalid response size/type')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('Nonfinite JSON constant')
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(result, dict):
        raise ValueError('Object required')
    return canonical(result)


async def extract_candidate(provider: ExtractionProvider, request: ExtractionRequest,
                            *, timeout_seconds=10, retry_limit=0):
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('Positive finite timeout required')
    if type(retry_limit) is not int or not 0 <= retry_limit <= 3:
        raise ValueError('Retry limit must be between zero and three')
    if any(not isinstance(v, str) or not v.strip() for v in (provider.name, provider.model)):
        raise ValueError('Provider identity required')
    attempts = []
    raw = candidate = None
    observed = None
    status = 'provider_error'
    for number in range(1, retry_limit + 2):
        started = time.monotonic()
        retry = False
        try:
            # asyncio.timeout preserves caller cancellation. A cooperative adapter
            # must honor cancellation; network SDK timeouts are also required.
            async with asyncio.timeout(timeout_seconds):
                response = await provider.extract(request)
                observed = response if isinstance(response, ProviderResponse) else None
                raw = response.text if observed else response
            candidate = parse_candidate(raw)
            status = 'candidate'
        except ProviderRefusal:
            status = 'refused'
        except IncompleteResponse:
            status = 'incomplete'
        except TimeoutError:
            raw = None
            status = 'timeout'
            retry = True
        except RetryableProviderError:
            status = 'provider_unavailable'
            retry = True
        except (ValueError, TypeError, RecursionError):
            status = 'invalid_response'
            raw = raw if isinstance(raw, str) and len(raw.encode()) <= 1000000 else None
        except Exception:
            # Provider exception messages may contain credentials or private data.
            status = 'provider_error'
        attempts.append(Attempt(number, status, (time.monotonic() - started) * 1000))
        if not retry:
            break
    return ExtractionResult(status, provider.name, provider.model, request.input_sha256,
                            request.input_version, request.prompt_version, request.schema_version,
                            tuple(attempts), raw, candidate,
                            observed.response_id if observed else None,
                            observed.input_tokens if observed else None,
                            observed.output_tokens if observed else None)


class DeterministicProvider:
    """Explicit test double. Never selects answers from input text or gold data."""
    name = 'deterministic-test-double'
    model = 'fixture-only'

    def __init__(self, response):
        self.response = response

    async def extract(self, request):
        return self.response
