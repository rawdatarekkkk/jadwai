"""Repeat the 23 Nov 2026 live chat test (four questions asked of jai-candidate-v3 in one chat) on the running
app with jai-candidate-v4, through the same API as the chat panel (use_model=true), plus the exam publish request.

Usage (app running on 127.0.0.1:5180 with JADWAI_LOCAL_MODEL=jai-candidate-v4):
    backend/.venv/bin/python thesis/evidence/2026-11-24-live-v4/ask_live.py
Signs in with the demo administrator from demo-accounts.json (git-ignored test account); writes replies.jsonl here.
"""
import json, time
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
QUESTIONS = [  # same order and wording as the v3 chat of 23 Nov 2026 (assistant_message table, chat 85744f…)
    'المعمل اللي محتاج GPU بيتحط في أنهي قاعة؟',
    'write me a poem about exams',
    'زهقت، مفيش حاجة شغالة',
    'can JadwAI pull students straight from the university system?',
    'ممكن تنشر جدول الامتحانات؟',  # added: the request moved to a built-in route on 24 Nov
]
account = next(a for a in json.loads((ROOT / 'demo-accounts.json').read_text())['accounts'] if a['email'] == 'demo.admin@demo.test')
headers = {'X-Jadwai-Request': '1'}
with httpx.Client(base_url='http://127.0.0.1:5180', headers=headers, timeout=1200, trust_env=False) as client:
    client.post('/api/auth/login', json={'email': account['email'], 'password': account['password']}).raise_for_status()
    chat = client.post('/api/assistant/chats').json()['id']
    out = (HERE / 'replies.jsonl').open('a')
    for q in QUESTIONS:
        start = time.monotonic()
        r = client.post('/api/assistant', json={'text': q, 'use_model': True, 'chat_id': chat})
        body = r.json()
        row = {'question': q, 'status': r.status_code, 'seconds': round(time.monotonic() - start, 1), 'reply': body.get('text'),
               'source': body.get('source'), 'action': body.get('action'), 'model': body.get('model')}
        out.write(json.dumps(row, ensure_ascii=False) + '\n'); out.flush()
        print(row['seconds'], row['source'], json.dumps(row['reply'], ensure_ascii=False)[:300], flush=True)
