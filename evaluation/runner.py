"""Offline, provider-neutral corpus validation and scoring. Makes no model calls."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import unicodedata

ROOT=Path(__file__).resolve().parent
DECISIONS={'ready','clarify','unsupported','conflict','mixed'}
TARGETS={'unavailable':('instructor_id','instructors'),'preferred_period':('instructor_id','instructors'),'room_unavailable':('room_id','rooms'),'group_unavailable':('group_id','groups'),'activity_allowed':('activity_id','activities'),'group_allowed':('group_id','groups')}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def audit(root,operation,split,reason):
    if split!='reserved':return
    if not reason or len(reason.strip())<8:raise ValueError('Reserved access requires a meaningful --reason; it is logged and is not a blind evaluation.')
    path=root/'access-log.jsonl'
    with path.open('a',encoding='utf-8') as out:
        out.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'operation':operation,'split':split,'reason':reason,'manifest_sha256':digest(read_json(root/'manifest.json'))},ensure_ascii=False)+'\n')


def load(root=ROOT,split='development',allow_reserved=False,reason='',operation='read'):
    if split not in ('development','reserved'):raise ValueError('Unknown split')
    if split=='reserved':
        if not allow_reserved:raise ValueError('Reserved data requires --allow-reserved and --reason')
        audit(root,operation,split,reason)
    manifest=read_json(root/'manifest.json')
    # Verify only selected cases plus shared context. Default development operations
    # do not read reserved cases or gold labels.
    for name in ('data/contexts.json',f'data/{split}/cases.jsonl',*(p for p in manifest['files'] if not p.startswith('data/'))):
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=manifest['files'][name]:raise ValueError('Manifest mismatch: '+name)
    contexts={c['id']:c for c in read_json(root/'data/contexts.json')}
    rows=read_rows(root/f'data/{split}/cases.jsonl')
    if len(rows)!=manifest['counts'][split]:raise ValueError('Manifest count mismatch')
    return manifest,contexts,rows


def entity(context,kind,ident):
    return type(ident) is str and any(r['id']==ident for r in context[kind])


def proposal_errors(p,context):
    if not isinstance(p,dict) or set(p)!={'kind','data'} or not isinstance(p.get('data'),dict):return ['proposal_structure']
    kind,d=p['kind'],p['data'];errors=[]
    if kind=='rule':
        target=TARGETS.get(d.get('type')) if type(d.get('type')) is str else None
        if target is None:return ['unsupported_rule_type']
        field,collection=target
        required={'type',field,'day','start_hour','end_hour','strength'}
        if not required<=set(d) or set(d)-required-{'title'}:errors.append('rule_fields')
        if not entity(context,collection,d.get(field)):errors.append('unknown_entity')
        if d.get('day') not in context['calendar']['days']:errors.append('outside_calendar')
        s,e=d.get('start_hour'),d.get('end_hour')
        if type(s) is not int or type(e) is not int or not context['calendar']['start_hour']<=s<e<=context['calendar']['end_hour']:errors.append('invalid_hours')
        if d.get('strength')!=('preferred' if d['type']=='preferred_period' else 'mandatory'):errors.append('invalid_strength')
        if 'title' in d and (type(d['title']) is not str or not 1<=len(d['title'].strip())<=100):errors.append('invalid_title')
    elif kind=='instructor_weekly_limit':
        if set(d)!={'instructor_id','max_weekly_hours'}:errors.append('weekly_limit_fields')
        if not entity(context,'instructors',d.get('instructor_id')):errors.append('unknown_entity')
        n=d.get('max_weekly_hours')
        if type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=168 or n*2!=int(n*2):errors.append('invalid_hours')
    elif kind=='realism_policy':
        if not d or set(d)-{'student_daily_hours','instructor_daily_hours'}:errors.append('policy_fields')
        for n in d.values():
            if type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=24 or n*2!=int(n*2):errors.append('invalid_hours')
    elif kind=='assignment_lock':
        if set(d)!={'source_run_id','activity_id','occurrence','keep_instructor','keep_time','keep_room'}:errors.append('lock_fields')
        if d.get('source_run_id')!=context['source_draft']['id']:errors.append('unknown_source')
        if not entity(context,'activities',d.get('activity_id')):errors.append('unknown_entity')
        if type(d.get('occurrence')) is not int or not any(a['activity_id']==d.get('activity_id') and a['occurrence']==d.get('occurrence') for a in context['source_draft']['assignments']):errors.append('unknown_occurrence')
        values=[d.get(k) for k in ('keep_instructor','keep_time','keep_room')]
        if any(type(v) is not bool for v in values) or not any(values):errors.append('invalid_lock_selection')
    else:errors.append('unsupported_proposal_kind')
    return errors


def output_errors(output,context):
    if not isinstance(output,dict) or set(output)!={'decision','proposals','clarifications','unsupported'}:return ['output_structure']
    errors=[]
    if type(output['decision']) is not str or output['decision'] not in DECISIONS:errors.append('decision')
    for field in ('proposals','clarifications','unsupported'):
        if not isinstance(output[field],list):errors.append(field+'_structure')
    if errors:return errors
    for field in ('clarifications','unsupported'):
        if any(type(x) is not str or not x for x in output[field]) or len(set(output[field]))!=len(output[field]):errors.append(field+'_codes')
    for p in output['proposals']:errors.extend(proposal_errors(p,context))
    decision=output['decision']
    if decision=='ready' and (not output['proposals'] or output['clarifications'] or output['unsupported']):errors.append('decision_consistency')
    if decision=='clarify' and not output['clarifications']:errors.append('decision_consistency')
    if decision=='unsupported' and (not output['unsupported'] or output['proposals']):errors.append('decision_consistency')
    if decision=='conflict' and (not output['clarifications'] or not output['proposals']):errors.append('decision_consistency')
    if decision=='mixed' and (not output['proposals'] or not (output['clarifications'] or output['unsupported'])):errors.append('decision_consistency')
    return errors


def canonical_proposal(p):
    d={k:v for k,v in p['data'].items() if k!='title'}
    # Numeric units are semantic numbers: 6 and 6.0 have the same meaning.
    d={k:(int(v) if type(v) is float and v.is_integer() else v) for k,v in d.items()}
    return {'kind':p['kind'],'data':d}


def bag(proposals):
    return Counter(json.dumps(canonical_proposal(p),sort_keys=True,ensure_ascii=False,separators=(',',':')) for p in proposals)


def field_bag(proposals):
    return Counter(json.dumps([p['kind'],key,value],sort_keys=True,ensure_ascii=False) for p in map(canonical_proposal,proposals) for key,value in p['data'].items())


def semantic_equal(a,b):
    return a['decision']==b['decision'] and bag(a['proposals'])==bag(b['proposals']) and set(a['clarifications'])==set(b['clarifications']) and set(a['unsupported'])==set(b['unsupported'])


def validate(root=ROOT,include_reserved=False,reason=''):
    seen=set();splits={};counts={};text_splits={}
    for split in ('development','reserved') if include_reserved else ('development',):
        _,contexts,rows=load(root,split,include_reserved,reason,'validate')
        families=set();langs=Counter();texts=set()
        for row in rows:
            if row['id'] in seen:raise ValueError('Duplicate case ID')
            seen.add(row['id']);families.add(row['family_id']);langs[row['language']]+=1
            normalized=' '.join(unicodedata.normalize('NFKC',row['text']).casefold().split())
            if normalized in texts:raise ValueError('Duplicate normalized input text')
            texts.add(normalized)
            if row['split']!=split or row['language'] not in ('en','ar','arz','mixed') or not row['text'].strip():raise ValueError('Case metadata error')
            if row['context_id'] not in contexts:raise ValueError('Unknown context')
            errors=output_errors(row['gold'],contexts[row['context_id']])
            if errors:raise ValueError(row['id']+': '+','.join(errors))
        for family in families:
            members=[r for r in rows if r['family_id']==family]
            if sorted(r['language'] for r in members)!=['ar','arz','en','mixed']:raise ValueError('Each family needs all four language categories')
            if len({digest(r['gold']) for r in members})!=1:raise ValueError('Translations disagree on gold')
        text_splits[split]=texts
        splits[split]=families;counts[split]={'cases':len(rows),'families':len(families),'languages':dict(langs)}
    if len(splits)==2 and splits['development']&splits['reserved']:raise ValueError('Family split leakage')
    if len(text_splits)==2 and text_splits['development']&text_splits['reserved']:raise ValueError('Normalized-text split leakage')
    return {'valid':True,'counts':counts,'adjudication':'draft_unreviewed','blind_test':False}


def ratio(a,b):return a/b if b else None


def metrics(tp,predicted,expected):
    precision=ratio(tp,predicted);recall=ratio(tp,expected)
    # An empty class has no measurable recall; it is not credited as success.
    return {'true_positive':tp,'predicted':predicted,'expected':expected,'precision':precision,'recall':recall,'f1':(2*tp/(predicted+expected)) if predicted+expected else None}


def score(rows,contexts,predictions,stage):
    ids={r['id'] for r in rows};pred={}
    for row in predictions:
        if not isinstance(row,dict) or row.get('id') not in ids:raise ValueError('Unknown prediction ID')
        if row['id'] in pred:raise ValueError('Duplicate prediction ID')
        pred[row['id']]=row
    counters=defaultdict(Counter);by_language=defaultdict(Counter);cases=[];metadata=defaultdict(list)
    exact=valid=decisions=unknown_entities=0
    for row in rows:
        expected=row['gold'];prediction=pred.get(row['id']);output=prediction.get('output') if prediction else None
        errors=output_errors(output,contexts[row['context_id']]);good=not errors
        valid+=good;correct=good and semantic_equal(expected,output);exact+=correct
        decisions+=isinstance(output,dict) and output.get('decision')==expected['decision']
        unknown_entities+='unknown_entity' in errors
        by_language[row['language']]['cases']+=1;by_language[row['language']]['exact']+=correct
        # Invalid outputs contribute no trusted proposals; they still count as a
        # failed complete case. Errors and candidate hallucinations remain visible.
        candidates=output.get('proposals',[]) if isinstance(output,dict) and isinstance(output.get('proposals'),list) else []
        proposed=[p for p in candidates if not proposal_errors(p,contexts[row['context_id']])]
        proposed_bag=bag(proposed)
        proposed_bag.update('invalid-proposal:'+digest(p) for p in candidates if proposal_errors(p,contexts[row['context_id']]))
        for name,expected_bag,predicted_bag in [('proposals',bag(expected['proposals']),proposed_bag),('fields',field_bag(expected['proposals']),field_bag(proposed)),('clarifications',Counter(expected['clarifications']),Counter(output['clarifications'] if good else [])),('unsupported',Counter(expected['unsupported']),Counter(output['unsupported'] if good else []))]:
            counters[name]['tp']+=sum((expected_bag&predicted_bag).values());counters[name]['predicted']+=sum(predicted_bag.values());counters[name]['expected']+=sum(expected_bag.values())
        meta=prediction.get('metadata',{}) if prediction else {}
        if not isinstance(meta,dict):raise ValueError('Prediction metadata must be an object')
        for key in ('latency_ms','cost_usd','attempts','input_tokens','output_tokens'):
            value=meta.get(key)
            if value is None:continue
            if type(value) not in (int,float) or not math.isfinite(value) or value<0 or (key in ('attempts','input_tokens','output_tokens') and (type(value) is not int or (key=='attempts' and value<1))):raise ValueError('Invalid metadata: '+key)
            metadata[key].append(value)
        cases.append({'id':row['id'],'language':row['language'],'family_id':row['family_id'],'received':prediction is not None,'valid_output':good,'errors':errors,'exact':bool(correct),'expected_sha256':digest(expected),'observed_sha256':digest(output)})
    family_results=[]
    for family in sorted({r['family_id'] for r in rows}):
        members=[r for r in rows if r['family_id']==family]
        outputs=[pred.get(r['id'],{}).get('output') for r in members]
        complete=all(o is not None and not output_errors(o,contexts[r['context_id']]) for r,o in zip(members,outputs))
        signatures=[digest({'decision':o['decision'],'proposals':sorted(bag(o['proposals']).items()),'clarifications':sorted(o['clarifications']),'unsupported':sorted(o['unsupported'])}) for o in outputs] if complete else []
        family_results.append({'family_id':family,'complete_valid':complete,'consistent':complete and len(set(signatures))==1,'all_exact':all(next(c['exact'] for c in cases if c['id']==r['id']) for r in members)})
    return {'family_consistency':{'family_count':len(family_results),'complete_valid_families':sum(f['complete_valid'] for f in family_results),'consistent_families':sum(f['consistent'] for f in family_results),'all_exact_families':sum(f['all_exact'] for f in family_results),'families':family_results},'stage':stage,'case_count':len(rows),'received_predictions':len(pred),'missing_predictions':len(rows)-len(pred),'valid_outputs':valid,'exact_cases':exact,'end_to_end_accuracy':ratio(exact,len(rows)),'decision_accuracy':ratio(decisions,len(rows)),'cases_with_unknown_entity_reference':unknown_entities,'metrics':{k:metrics(c['tp'],c['predicted'],c['expected']) for k,c in counters.items()},'by_language':{k:{**dict(v),'end_to_end_accuracy':ratio(v['exact'],v['cases'])} for k,v in by_language.items()},'telemetry':{k:{'observed_cases':len(metadata[k]),'missing_cases':len(rows)-len(metadata[k]),'sum':sum(metadata[k]) if metadata[k] else None,'mean':ratio(sum(metadata[k]),len(metadata[k]))} for k in ('latency_ms','cost_usd','attempts','input_tokens','output_tokens')},'cases':cases,
       'definitions':{'exact':'Decision, complete proposal multiset (titles ignored), clarification codes and unsupported codes must all match. Invalid or missing output fails the case.','fields':'Conditional diagnostic over individually schema-valid proposals. Micro bag-of-fields diagnostic; it can miss cross-proposal field association errors. Strict proposal and full-case metrics preserve associations.','proposal_precision':'Every attempted invalid proposal is a false positive; missing or invalid full envelopes still fail end-to-end. Valid proposals can be evaluated separately from envelope errors.', 'consistency':'Translations of a family must all yield the same valid semantic output; consistency alone does not establish correctness.', 'telemetry':'Only supplied measured values are summarised. Missing cost/latency is unknown, not zero. Attempts includes the first request.','scope':'Scores against unreviewed synthetic draft labels are development diagnostics, not research findings. No provider is called by this tool.'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','export-inputs','score'])
    parser.add_argument('--split',choices=['development','reserved'],default='development')
    parser.add_argument('--allow-reserved',action='store_true');parser.add_argument('--reason',default='')
    parser.add_argument('--include-reserved',action='store_true')
    parser.add_argument('--predictions',type=Path);parser.add_argument('--config',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--stage',choices=['raw','post_review'],default='raw')
    args=parser.parse_args()
    if args.command=='validate':
        if args.include_reserved and not args.allow_reserved:parser.error('--include-reserved requires --allow-reserved')
        print(json.dumps(validate(include_reserved=args.include_reserved,reason=args.reason),ensure_ascii=False,indent=2));return
    manifest,contexts,rows=load(split=args.split,allow_reserved=args.allow_reserved,reason=args.reason,operation=args.command)
    if not args.output:parser.error('--output is required')
    if args.output.resolve().is_relative_to((ROOT/'data').resolve()) or args.output.resolve() in {(ROOT/'manifest.json').resolve(),(ROOT/'access-log.jsonl').resolve()}:parser.error('Output cannot overwrite dataset or audit files')
    if args.output.exists():parser.error('Output already exists; choose a fresh path')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.command=='export-inputs':
        context_path=args.output.with_name(args.output.stem+'-contexts.json')
        if context_path.exists():parser.error('Context companion already exists; choose a fresh output path')
        args.output.write_text(''.join(json.dumps({k:r[k] for k in ('id','language','context_id','text')},ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        context_path.write_text(json.dumps(list(contexts.values()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Exported gold-free inputs and shared contexts.');return
    if not args.predictions or not args.config:parser.error('--predictions and --config are required')
    config=read_json(args.config)
    if not isinstance(config,dict) or not all(type(config.get(k)) is str and config[k] for k in ('provider','model','prompt_version','schema_version')):parser.error('Config must identify provider/model/prompt_version/schema_version')
    result=score(rows,contexts,read_rows(args.predictions),args.stage)
    result.update(scorer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),dataset_version=manifest['dataset_version'],manifest_sha256=digest(manifest),configuration_sha256=digest(config),configuration=config,predictions_sha256=hashlib.sha256(args.predictions.read_bytes()).hexdigest(),created_at=datetime.now(timezone.utc).isoformat(),split=args.split,reserved_is_blind=False,independently_adjudicated=False)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('case_count','received_predictions','exact_cases','end_to_end_accuracy','stage','split')},indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError) as exc:
        print('Evaluation input error: '+str(exc),file=sys.stderr);sys.exit(2)
