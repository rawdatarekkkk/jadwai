"""Score a locally hosted model (Ollama) on the development-v2 corpus with the project's own scorer.

Sends each sentence through the same LocalProvider and extract_candidate path the app uses,
with the same instructions and JSON schema as the GPT adapter. Resumable: each answer is
appended to predictions.jsonl, so a stopped run continues where it left off.

    python score_local_model.py [--model qwen2.5:7b-instruct] [--limit N] [--score-only]
"""
import argparse, asyncio, collections, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'backend'))
from evaluation.development import load_bundle
from evaluation import harness
from app.extraction import ExtractionRequest, extract_candidate
from app.local_provider import LocalProvider
from app.openai_provider import PROMPT_VERSION

KINDS = {'instructors': 'instructors', 'rooms': 'rooms', 'groups': 'groups', 'activities': 'courses'}


def records(ctx):
    """The same record shape the app sends (and the built-in parser was scored with)."""
    out = []
    for key, kind in KINDS.items():
        for e in ctx.get(key, []):
            out.append({'id': e['id'], 'kind': kind, 'data': {'name': e['name'], 'code': e['id'], **({'activity_type': e.get('activity_type')} if e.get('activity_type') else {})}})
    return out


def adapt(out):
    """The same format adapter as the parser baseline: drop empty optional fields, whole hours as integers."""
    whole = lambda v: int(v) if type(v) is float and v.is_integer() else v
    props = []
    for p in out.get('proposals') or []:
        data = p.get('data') or {}
        clean = {k: whole(v) for k, v in data.items() if v is not None and k not in ('title', 'params')}
        params = {k: v for k, v in (data.get('params') or {}).items() if v is not None}
        if params: clean['params'] = params
        props.append({'kind': p.get('kind'), 'data': clean})
    return {**out, 'proposals': props}


async def main(args):
    manifest, contexts, rows = load_bundle(ROOT / 'evaluation' / 'development-v2')
    preds_path = HERE / f'predictions-{args.model.replace(":", "_")}.jsonl'
    done = {json.loads(l)['id']: json.loads(l) for l in preds_path.read_text().splitlines()} if preds_path.exists() else {}
    provider = LocalProvider(args.model, timeout_seconds=args.timeout)
    todo = [r for r in rows if r['id'] not in done][: args.limit or None]
    if not args.score_only:
        for i, row in enumerate(todo, 1):
            ctx = contexts[row['context_id']]
            req = ExtractionRequest.create(row['text'], {'records': records(ctx), 'calendar': ctx['calendar']}, 1, PROMPT_VERSION, 'proposal-contract-v1')
            started = time.monotonic()
            result = await extract_candidate(provider, req, timeout_seconds=args.timeout + 5)
            ms = round((time.monotonic() - started) * 1000)
            output = adapt(json.loads(result.candidate_json)) if result.status == 'candidate' else None
            meta = {'latency_ms': ms, 'attempts': len(result.attempts), 'cost_usd': 0,
                    **({'input_tokens': result.input_tokens} if result.input_tokens is not None else {}),
                    **({'output_tokens': result.output_tokens} if result.output_tokens is not None else {})}
            pred = {'id': row['id'], 'output': output, 'status': result.status, 'metadata': meta}
            done[row['id']] = pred
            with preds_path.open('a') as f: f.write(json.dumps(pred, ensure_ascii=False) + '\n')
            print(f"[{len(done)}/{len(rows)}] {row['id']} {result.status} {ms/1000:.1f}s", flush=True)
    scored = [r for r in rows if r['id'] in done]
    if not scored: return
    preds = [{k: v for k, v in done[r['id']].items() if k != 'status'} for r in scored]
    result = harness.clustered_score(scored, contexts, preds, 'raw', 1000, 42) if len(scored) == len(rows) else harness.base.score(scored, contexts, preds, 'raw')
    json.dump({'model': args.model, 'cases': len(scored), 'statuses': collections.Counter(done[r['id']]['status'] for r in scored), 'result': result},
              open(HERE / f'score-{args.model.replace(":", "_")}.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print('model', args.model, 'cases', result['case_count'], 'exact', result['exact_cases'], 'decision_acc', round(result['decision_accuracy'], 3))
    print('statuses', dict(collections.Counter(done[r['id']]['status'] for r in scored)))
    lat = sorted(done[r['id']]['metadata']['latency_ms'] for r in scored)
    print('median latency', lat[len(lat) // 2] / 1000, 's')
    by = collections.defaultdict(list)
    for r in scored: by[r['language']].append(r)
    pm = {p['id']: p for p in preds}
    for lang, members in by.items():
        s = harness.base.score(members, contexts, [pm[m['id']] for m in members], 'raw')
        print('lang', lang, 'n', s['case_count'], 'exact', s['exact_cases'], 'decision_acc', round(s['decision_accuracy'], 3))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model', default='qwen2.5:7b-instruct'); p.add_argument('--limit', type=int, default=0)
    p.add_argument('--timeout', type=float, default=300); p.add_argument('--score-only', action='store_true')
    asyncio.run(main(p.parse_args()))
