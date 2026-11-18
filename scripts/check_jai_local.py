"""Non-mutating smoke check against the configured local Ollama model."""
import asyncio
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend' / 'tests'))
from app.main import app
from app.assistant import model_settings
from app.assistant_capabilities import converse
from test_assistant import VIEW

async def main():
    settings = model_settings()
    if not settings:
        raise SystemExit('Local model must be enabled')
    history = []
    for message in [
        'Before changing anything, explain how giving our students two free days could affect shared lectures and other groups.',
        'Could we keep their shared lectures fixed, then? Please explain; do not change anything yet.',
        'What criteria should I use to compare two timetable drafts? Just explain, do not change anything.',
    ]:
        start = time.monotonic()
        reply = await converse(message, VIEW, history, settings, app)
        print(json.dumps({'message': message, 'seconds': round(time.monotonic()-start, 1), 'reply': reply}, ensure_ascii=False), flush=True)
        if not reply or reply.get('action') or any('did not finish' in line for line in reply.get('text', [])):
            raise SystemExit('Expected a conversational answer with no mutation')
        history += [{'role': 'user', 'content': message}, {'role': 'assistant', 'content': '\n'.join(reply['text'])}]

asyncio.run(main())
