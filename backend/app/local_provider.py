"""A locally hosted model (Ollama) for interpreting typed constraints.

It sends the same instructions and JSON schema as the GPT adapter, so its output goes through
the same validation, review, draft and approval steps. Nothing leaves the machine that runs
the model. Enabled with:

    JADWAI_AI_ENABLED=true
    JADWAI_AI_PROVIDER=local
    JADWAI_LOCAL_MODEL=qwen2.5:7b-instruct      # any model pulled with `ollama pull`
    JADWAI_LOCAL_URL=http://127.0.0.1:11434     # where Ollama listens (a GPU server also works)
    JADWAI_LOCAL_TIMEOUT_SECONDS=180            # CPU-only machines need minutes, not seconds
"""
import json
import os
import re
import httpx
from app.extraction import ExtractionRequest, IncompleteResponse, ProviderResponse, RetryableProviderError
from app.openai_provider import INSTRUCTIONS, PROMPT_VERSION, output_schema
from app.rule_parser import find_records, mentions, normalise, plain

DEFAULT_MODEL = 'qwen2.5:7b-instruct'
DEFAULT_URL = 'http://127.0.0.1:11434'
SMALL = 60          # contexts up to this many records are sent whole
MAX_RECORDS = 40    # otherwise, at most this many records the text mentions
KEEP = ('name', 'code', 'activity_type', 'position')


def relevant_context(text, context):
    """A small model cannot read a whole university (hundreds of records, ~100k tokens), so send
    only the records the text names, plus every record sharing an ambiguous name part, so the model
    can still ask which one is meant. Small contexts are sent whole."""
    calendar = context.get('calendar') or {}
    periods = calendar.get('teaching_periods') or []
    if not periods and all(k in calendar for k in ('start_hour', 'end_hour', 'period_minutes')):
        step = calendar['period_minutes']
        periods = [{'start': start, 'end': start + step} for start in range(round(calendar['start_hour'] * 60), round(calendar['end_hour'] * 60) - step + 1, step)]
    if periods:
        context = {**context, 'calendar': {**calendar, 'slot_reference': [
            {'number': i + 1, 'start_hour': slot['start'] / 60, 'end_hour': slot['end'] / 60}
            for i, slot in enumerate(periods)]}}
    records = context.get('records') or []
    slim = lambda r: {'id': r['id'], 'kind': r['kind'], 'data': {k: v for k, v in (r.get('data') or {}).items() if k in KEEP}}
    if len(records) <= SMALL:
        return {**context, 'records': [slim(r) for r in records]}
    said, chosen = normalise(text), {}
    for kind in sorted({r['kind'] for r in records}):
        found, ambiguous = find_records(said, records, kind)
        chosen.update({r['id']: r for r in found})
        for r in records:
            if r['kind'] == kind and any(mentions(plain((r.get('data') or {}).get('name', '')), part) for part in ambiguous):
                chosen[r['id']] = r
    return {**context, 'records': [slim(r) for r in list(chosen.values())[:MAX_RECORDS]],
            'note': f'Only the records this requirement mentions are listed (of {len(records)}). If a named record is not listed, ask a clarification.'}


CODE = {'type': 'string', 'pattern': '^[a-z][a-z0-9_]{2,59}$'}


def local_schema():
    """The production proposal schema, reordered for a small local model. Ollama generates fields in
    schema order, so with `decision` first the model committed to a decision before writing its
    proposal, and it wrote prose explanations where short codes belong (every statement then came
    back "unsupported"). Proposals come first and the decision last, and clarification and
    unsupported items must be short snake_case codes. Validation is unchanged."""
    schema = output_schema()
    props = schema['properties']
    order = ['proposals', 'clarifications', 'unsupported', 'decision']
    assert set(order) == set(props)
    schema['properties'] = {k: props[k] for k in order}
    schema['required'] = order
    for key in ('clarifications', 'unsupported'):
        schema['properties'][key] = {**props[key], 'items': CODE}
    return schema


class LocalProvider:
    name = 'ollama'

    def __init__(self, model=DEFAULT_MODEL, url=DEFAULT_URL, *, transport=None, timeout_seconds=180):
        if not isinstance(model, str) or not model.strip():
            raise ValueError('Local model name required')
        if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            raise ValueError('Local model URL required')
        self.model, self.url = model.strip(), url.rstrip('/')
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def configured(cls):
        if os.environ.get('JADWAI_AI_ENABLED', '').lower() != 'true' or os.environ.get('JADWAI_AI_PROVIDER', '').lower() != 'local':
            raise ValueError('Local model calls are disabled')
        try:
            timeout = float(os.environ.get('JADWAI_LOCAL_TIMEOUT_SECONDS', '180'))
        except ValueError:
            raise ValueError('Invalid timeout') from None
        if not 5 <= timeout <= 900:
            raise ValueError('Invalid timeout')
        return cls(os.environ.get('JADWAI_LOCAL_MODEL', DEFAULT_MODEL), os.environ.get('JADWAI_LOCAL_URL', DEFAULT_URL), timeout_seconds=timeout)

    async def extract(self, request: ExtractionRequest):
        if request.prompt_version != PROMPT_VERSION or request.schema_version != 'proposal-contract-v1':
            raise ValueError('Unsupported prompt/schema version')
        preliminary = []
        from app.teaching_language import eligible, FRAME, INSTRUCTION, compile_frame
        if eligible(request.text) and all(key in json.loads(request.context_json).get('calendar', {}) for key in ('start_hour', 'end_hour')):
            # A small semantic frame avoids asking the 7B model to perform calendar
            # arithmetic while also copying the full database-rule schema.
            frame_payload = {'model': self.model, 'stream': False, 'keep_alive': '30m',
                'format': FRAME, 'options': {'temperature': 0, 'seed': 42, 'num_ctx': 8192, 'num_predict': 360},
                'messages': [{'role':'system','content':INSTRUCTION}, {'role':'user','content':json.dumps({'requirement':request.text},ensure_ascii=False)}]}
            try:
                async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout_seconds, follow_redirects=False, trust_env=False) as client:
                    response = await client.post(self.url+'/api/chat',json=frame_payload)
                response.raise_for_status()
                data=response.json()
                frame=json.loads((data.get('message') or {}).get('content',''))
                if not data.get('done'):raise IncompleteResponse('Local frame incomplete')
                compiled=compile_frame(frame,request.text,json.loads(request.context_json)['calendar'])
                if compiled is not None:
                    return ProviderResponse(json.dumps(compiled,ensure_ascii=False), None, data.get('prompt_eval_count'), data.get('eval_count'))
                preliminary.append(data)
            except httpx.TimeoutException:
                raise TimeoutError('Local model timeout') from None
            except httpx.HTTPError:
                raise RetryableProviderError('Local model unavailable') from None
            except (ValueError, KeyError, TypeError):
                raise ValueError('Invalid local semantic frame') from None

        payload = {'model': self.model, 'stream': False, 'keep_alive': '30m',
                   'format': local_schema(),  # Ollama constrains decoding to this JSON schema
                   'options': {'temperature': 0, 'seed': 42, 'num_ctx': 8192, 'num_predict': 1800},
                   'messages': [{'role': 'system', 'content': INSTRUCTIONS},
                                {'role': 'user', 'content': json.dumps({'requirement': request.text, 'context': relevant_context(request.text, json.loads(request.context_json))}, ensure_ascii=False)}]}
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout_seconds, follow_redirects=False, trust_env=False) as client:
                response = await client.post(self.url + '/api/chat', json=payload)
        except httpx.TimeoutException:
            raise TimeoutError('Local model timeout') from None
        except httpx.TransportError:
            raise RetryableProviderError('Local model not reachable; is Ollama running?') from None
        if response.status_code == 404:
            raise RuntimeError('Local model not found; pull it with ollama pull')
        if response.status_code >= 500 or response.status_code in (408, 429):
            raise RetryableProviderError('Temporary local model error')
        if response.status_code != 200 or len(response.content) > 2_000_000:
            raise RuntimeError('Local model request rejected')
        data = response.json()
        if not data.get('done'):
            raise IncompleteResponse('Local model did not finish')
        text = (data.get('message') or {}).get('content')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('One structured output required')
        # JSON-constrained decoding alone cannot enforce meanings (known IDs, calendar bounds,
        # required versus preferred, or consistent decisions). Give the model one bounded
        # correction using validator errors; the normal completion validator still has the final say.
        from app.proposal_validation import validate_proposal
        observations = preliminary + [data]
        context = json.loads(request.context_json)
        try:
            candidate = json.loads(text)
        except ValueError:
            candidate = None
        if isinstance(candidate, dict) and context.get('records') and context.get('calendar'):
            checked = validate_proposal(candidate, records={r['id']: r['kind'] for r in context['records']}, calendar=context['calendar'])
            if not checked.valid:
                payload['messages'] += [{'role': 'assistant', 'content': text}, {'role': 'user', 'content': json.dumps({
                    'validation_errors': checked.errors,
                    'instruction': 'Correct the previous JSON using only the original requirement and supplied context. Do not change its meaning to satisfy validation. Unavailability is mandatory, never preferred. Before T ends at T; after T starts at T. Use calendar start/end for the other edge. A ready response has proposals and empty clarifications/unsupported. If a required detail is unknown, return clarify with no invented values. Return the complete JSON.'})}]
                try:
                    async with httpx.AsyncClient(transport=self._transport, timeout=self.timeout_seconds, follow_redirects=False, trust_env=False) as client:
                        repaired = await client.post(self.url + '/api/chat', json=payload)
                    if repaired.status_code == 200 and len(repaired.content) <= 2_000_000:
                        fixed = repaired.json()
                        observations.append(fixed)
                        fixed_text = (fixed.get('message') or {}).get('content')
                        if fixed.get('done') and isinstance(fixed_text, str):
                            fixed_candidate = json.loads(fixed_text)
                            if validate_proposal(fixed_candidate, records={r['id']: r['kind'] for r in context['records']}, calendar=context['calendar']).valid:
                                text = fixed_text
                except (httpx.HTTPError, ValueError, TypeError):
                    pass  # preserve the original invalid candidate for the normal rejection path

        # An explicit preference must never become a hard constraint on review.
        # Ambiguous/mixed prose is left to the model and human reviewer.
        explicit_soft = re.match(r'^\s*(?:preferred|preferably|ideally|soft(?: constraint)?|if possible|يفضل|مفضل)\b', request.text, re.I)
        explicit_hard = re.match(r'^\s*(?:mandatory|required|hard(?: constraint)?|must)\b', request.text, re.I)
        try:
            final = json.loads(text)
            rules = [item['data'] for item in final.get('proposals', [])]
            if rules and ((explicit_soft and not re.search(r'\b(?:must|required|mandatory)\b', request.text, re.I) and any(rule.get('strength') != 'preferred' for rule in rules)) or
                          (explicit_hard and not re.search(r'\b(?:prefer|preferred|ideally|soft)\b', request.text, re.I) and any(rule.get('strength') != 'mandatory' for rule in rules))):
                text = json.dumps({'decision': 'clarify', 'proposals': [], 'clarifications': ['constraint_strength_mismatch'], 'unsupported': []})
        except (ValueError, KeyError, TypeError):
            pass

        tokens = []
        for key in ('prompt_eval_count', 'eval_count'):
            counts = [item.get(key) for item in observations]
            tokens.append(sum(counts) if all(type(v) is int and v >= 0 for v in counts) else None)
        return ProviderResponse(text, None, *tokens)
