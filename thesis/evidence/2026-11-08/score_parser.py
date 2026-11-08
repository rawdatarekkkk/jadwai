"""Score JadwAI's built-in parser on the development-v2 corpus with the project's own scorer."""
import json, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'backend'))
from evaluation.development import load_bundle
from evaluation import harness
from app.rule_parser import parse
manifest, contexts, rows = load_bundle(ROOT / 'evaluation' / 'development-v2')
KINDS = {'instructors': 'instructors', 'rooms': 'rooms', 'groups': 'groups', 'activities': 'courses'}
def records(ctx):
    out = []
    for key, kind in KINDS.items():
        for e in ctx.get(key, []):
            out.append({'id': e['id'], 'kind': kind, 'data': {'name': e['name'], 'code': e['id'], **({'activity_type': e.get('activity_type')} if e.get('activity_type') else {})}})
    return out
preds = []
for row in rows:
    ctx = contexts[row['context_id']]
    out = parse(row['text'], {'records': records(ctx), 'calendar': ctx['calendar']})
    out = {**out, 'proposals': [{'kind': 'rule', 'data': {k: v for k, v in p['data'].items() if v is not None and k not in ('title', 'params')} | ({'params': {k: v for k, v in p['data']['params'].items() if v is not None}} if any(v is not None for v in (p['data'].get('params') or {}).values()) else {})} for p in out['proposals']]}
    # Format adapter: the evaluation contract stores whole hours as integers (10, not 10.0).
    whole = lambda v: int(v) if type(v) is float and v.is_integer() else v
    out['proposals'] = [{**p, 'data': {k: whole(v) for k, v in p['data'].items()}} for p in out['proposals']]
    preds.append({'id': row['id'], 'output': out})
result = harness.clustered_score(rows, contexts, preds, 'raw', 1000, 42)
json.dump({'result': result, 'predictions': preds}, open(Path(__file__).with_name('parser_score.json'), 'w'), ensure_ascii=False, indent=1, default=str)
print('cases', result['case_count'], 'exact', result['exact_cases'])
for k, v in result['uncertainty']['intervals'].items():
    if v['estimate'] is not None and ('accuracy' in k or k.endswith('.f1')):
        print(f"{k:45s} {v['estimate']:.3f}  [{v['lower']:.3f}, {v['upper']:.3f}]")
# Per language
by = collections.defaultdict(list)
for row in rows: by[row['language']].append(row)
pm = {p['id']: p for p in preds}
for lang, members in by.items():
    r = harness.base.score(members, contexts, [pm[m['id']] for m in members], 'raw')
    print('lang', lang, 'n', r['case_count'], 'exact', r['exact_cases'], 'decision_acc', round(r['decision_accuracy'], 3))
