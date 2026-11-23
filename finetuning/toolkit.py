"""Local-only dataset validation, export and non-mutating Ollama evaluation."""
import argparse,hashlib,json,random,re,time,urllib.request,urllib.error
from pathlib import Path
from build_dataset import digest
BASE=Path(__file__).parent

def schema_check(value,schema):
 types=schema.get('type');types=types if isinstance(types,list) else [types] if types else []
 checks={'object':lambda:type(value)is dict,'array':lambda:type(value)is list,'string':lambda:type(value)is str,'boolean':lambda:type(value)is bool,'integer':lambda:type(value)is int,'number':lambda:type(value)in(int,float),'null':lambda:value is None}
 if types and not any(checks[t]() for t in types):raise ValueError('Wrong JSON field type')
 if 'enum' in schema and value not in schema['enum']:raise ValueError('Unknown enum value')
 if isinstance(value,dict):
  if set(schema.get('required',[]))-value.keys():raise ValueError('Missing fields')
  if schema.get('additionalProperties') is False and value.keys()-schema.get('properties',{}).keys():raise ValueError('Unexpected fields')
  for k,v in value.items():
   if k in schema.get('properties',{}):schema_check(v,schema['properties'][k])
 if isinstance(value,list):
  for v in value:schema_check(v,schema.get('items',{}))

def load():
 manifest=json.loads((BASE/'data/manifest.json').read_text());rows=[]
 for name,sha in manifest['files'].items():
  raw=(BASE/'data'/name).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Dataset changed: rebuild and repeat review')
  for line in raw.decode().splitlines():
   row=json.loads(line);copy=dict(row);sha=copy.pop('sha256')
   if digest(copy)!=sha:raise ValueError('Row hash mismatch')
   schema_check(row['target'],row['schema']);rows.append(row)
 ids=[r['id'] for r in rows]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate IDs')
 train={r['family'] for r in rows if r['split']=='train'};test={r['family'] for r in rows if r['split']=='test'}
 if train&test:raise ValueError('Family leakage')
 prompts=[digest(r['messages']) for r in rows]
 if len(prompts)!=len(set(prompts)):raise ValueError('Duplicate prompts')
 return rows

def reviewed(rows,path,split):
 reviews=json.loads(Path(path).read_text())['reviews'];approved={}
 for r in reviews:
  if r['family'] in approved:raise ValueError('Duplicate family review')
  approved[r['family']]=r
 selected=[]
 for family in {r['family'] for r in rows if r['split']==split}:
  items=[r for r in rows if r['family']==family];review=approved.get(family,{})
  if review.get('approved') is True and review.get('reviewer','').strip() and review.get('rationale','').strip() and review.get('family_sha256')==digest([r['sha256'] for r in items]):selected.extend(items)
 if not selected:raise ValueError('No approved examples. A human must review the draft families first.')
 return sorted(selected,key=lambda r:r['id'])

def export(rows,path,out):
 selected_splits={split:reviewed(rows,path,split) for split in ('train','test')}
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 for split in ('train','test'):
  selected=selected_splits[split]
  data=[{'prompt':r['messages'],'completion':[{'role':'assistant','content':json.dumps(r['target'],ensure_ascii=False)}]} for r in selected]
  dest=out/f'{split}.jsonl'
  with dest.open('x') as f:
   for item in data:f.write(json.dumps(item,ensure_ascii=False)+'\n')
 provenance={'dataset_manifest':hashlib.sha256((BASE/'data/manifest.json').read_bytes()).hexdigest(),'review_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'files':{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('train.jsonl','test.jsonl')}}
 (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')

def evaluate(rows,args):
 # Fixed localhost only: no website endpoints, secrets, tools or mutations.
 chosen=[r for r in rows if r['split']=='test' and r['task']==args.task]
 # One wording per family by default (per family and language for conversations); no inflated repeated-paraphrase score.
 families={}
 for r in chosen:families.setdefault(r['id'] if args.all_wordings else (r['family'],r.get('language')) if r['task']=='conversation' else r['family'],r)
 chosen=list(families.values())[:args.limit]
 if args.ids:chosen=[r for r in rows if r['split']=='test' and r['task']==args.task and r['id'] in set(args.ids)]  # rerun specific cases, e.g. after timeouts
 if not chosen:raise ValueError('No cases selected')
 results=[]
 out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('x') as f:
  for row in chosen:
   start=time.monotonic();prediction=None;error=None;valid=False
   try:
    payload={'model':args.model,'stream':False,'keep_alive':'30m','messages':row['messages'],'format':row['schema'],'options':{'temperature':0,'seed':42,'num_ctx':8192,'num_predict':360 if row['task']=='frame' else 350 if row['task']=='conversation' else 1100}}
    request=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    # Ignore ambient proxy settings for localhost traffic.
    response=json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=args.timeout))
    if not response.get('done'):raise ValueError('Model generation incomplete')
    raw=response['message']['content']
    try:prediction=json.loads(raw)
    except ValueError:
     # Same rescue as the live chat: a reply cut off mid-loop keeps its complete sentences, never an action.
     from app.assistant_capabilities import salvage_reply
     prediction=salvage_reply(raw) if row['task']=='conversation' else None
     if prediction is None:raise
    schema_check(prediction,row['schema']);valid=True
   except (ValueError,KeyError,TypeError,OSError) as e:error=str(e)
   matched=valid and all(prediction.get(k)==row['target'].get(k) for k in row['score_keys'])
   result={'id':row['id'],'family':row['family'],'task':row['task'],'row_sha256':row['sha256'],'model':args.model,'seconds':round(time.monotonic()-start,2),'schema_valid':valid,'semantic_match':matched,'prediction':prediction,'error':error,'labels_status':'synthetic draft; human review pending','scope':'model output only; no website action executed; reply quality not automatically scored'}
   if row['task']=='conversation':result.update(reply_checks(row,prediction if valid else None))
   f.write(json.dumps(result,ensure_ascii=False)+'\n');f.flush();results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
 summary={'cases':len(results),'semantic_matches':sum(r['semantic_match'] for r in results),'schema_valid':sum(r['schema_valid'] for r in results),'mean_seconds':round(sum(r['seconds'] for r in results)/len(results),2),'note':'Engineering diagnostic on draft labels, not a research accuracy finding.'}
 if args.task=='conversation':summary.update(no_action=sum(r['semantic_match'] for r in results),language_match=sum(bool(r.get('language_match')) for r in results),within_80_words=sum(bool(r.get('within_80_words')) for r in results),note='Automatic checks only cover action choice, language and length. Reply quality needs the blind rating sheet.')
 print(json.dumps(summary))

ARABIC=re.compile(r'[\u0600-\u06FF]')
INTERNAL=re.compile(r'/api/|\b(?:room|ins|group|course|act|run|exam)-[a-z0-9]+\b')

def reply_checks(row,prediction):
 from app.assistant_capabilities import clean_reply
 raw_reply=(prediction or {}).get('reply') or ''
 reply=clean_reply(raw_reply)  # what the live chat shows after removing repeated sentences
 return {'reply':reply,'raw_reply':raw_reply,'reference':row['target']['reply'],'language':row['language'],'words':len(reply.split()),'within_80_words':bool(reply) and len(reply.split())<=80,
         'language_match':bool(reply) and bool(ARABIC.search(reply))==(row['language']=='ar'),'exposes_internal':bool(INTERNAL.search(reply))}

def sheet(args):
 """Blind side-by-side rating sheet for two conversation runs; the A/B key is written to a separate file."""
 runs=[{r['id']:r for r in map(json.loads,Path(f).read_text().splitlines())} for f in args.runs]
 rows={r['id']:r for r in load()};ids=sorted(set(runs[0])&set(runs[1]))
 if not ids:raise ValueError('The two runs share no cases')
 rng=random.Random(args.seed);key={};lines=['# JAI blind reply rating','','For each case, score reply A and reply B from 1 (poor) to 5 (excellent) on: correct and grounded in the facts, logical reasoning, helpful next step, natural language. Do not open the key file until every case is scored.','']
 for n,ident in enumerate(ids,1):
  row=rows[ident];payload=json.loads(row['messages'][-1]['content']);order=[0,1];rng.shuffle(order);key[ident]={'A':args.runs[order[0]],'B':args.runs[order[1]]}
  lines += [f'## {n}. {ident}','']+[f"> {m['role']}: {m['content']}" for m in row['messages'][1:-1]]+[f"**User:** {payload['message']}",'',f"**Reference:** {row['target']['reply']}",'']
  for label,which in zip('AB',order):lines += [f"**Reply {label}:** {(runs[which][ident].get('prediction') or {}).get('reply') or '(no valid reply)'}",'',f'Score {label}: correct __ logical __ helpful __ natural __','']
 Path(args.output).write_text('\n'.join(lines));Path(args.output).with_suffix('.key.json').write_text(json.dumps(key,indent=2))
 print(json.dumps({'cases':len(ids),'sheet':args.output,'key':str(Path(args.output).with_suffix('.key.json'))}))

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 sub.add_parser('validate')
 ex=sub.add_parser('export');ex.add_argument('--reviews',required=True);ex.add_argument('--output',required=True)
 ev=sub.add_parser('evaluate');ev.add_argument('--model',required=True);ev.add_argument('--task',choices=['frame','selection','arguments','conversation'],default='frame');ev.add_argument('--all-wordings',action='store_true');ev.add_argument('--limit',type=int,default=3);ev.add_argument('--timeout',type=int,default=180);ev.add_argument('--output',required=True);ev.add_argument('--ids',nargs='+',help='evaluate only these row ids (ignores --limit)')
 sh=sub.add_parser('sheet');sh.add_argument('--runs',nargs=2,required=True);sh.add_argument('--output',required=True);sh.add_argument('--seed',type=int,default=7)
 args=p.parse_args()
 if args.command=='sheet':return sheet(args)
 rows=load()
 if args.command=='validate':print(json.dumps({'rows':len(rows),'families':len({r['family'] for r in rows}),'train':sum(r['split']=='train' for r in rows),'test':sum(r['split']=='test' for r in rows),'status':'structurally valid; human review pending'}))
 elif args.command=='export':export(rows,args.reviews,args.output)
 else:evaluate(rows,args)
if __name__=='__main__':main()
