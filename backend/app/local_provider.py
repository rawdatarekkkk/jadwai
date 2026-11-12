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
import httpx
from app.extraction import ExtractionRequest, IncompleteResponse, ProviderResponse, RetryableProviderError
from app.openai_provider import INSTRUCTIONS, PROMPT_VERSION, output_schema

DEFAULT_MODEL = 'qwen2.5:7b-instruct'
DEFAULT_URL = 'http://127.0.0.1:11434'


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
        payload = {'model': self.model, 'stream': False, 'keep_alive': '30m',
                   'format': output_schema(),  # Ollama constrains decoding to this JSON schema
                   'options': {'temperature': 0, 'seed': 42},
                   'messages': [{'role': 'system', 'content': INSTRUCTIONS},
                                {'role': 'user', 'content': json.dumps({'requirement': request.text, 'context': json.loads(request.context_json)}, ensure_ascii=False)}]}
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
        tokens = [data.get('prompt_eval_count'), data.get('eval_count')]
        tokens = [v if type(v) is int and v >= 0 else None for v in tokens]
        return ProviderResponse(text, None, *tokens)
