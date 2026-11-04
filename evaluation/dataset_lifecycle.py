"""Prepare reproducible family splits and seal externally reviewed material.

No existing draft or reserved data is promoted. Identity, consent and independence
metadata are operator declarations, not facts verified by this program.
"""
import argparse,hashlib,json,random,shutil,tempfile
from datetime import datetime,timezone
from collections import defaultdict
from pathlib import Path
try:
 from . import runner
 from .development import normalized,write_new
except ImportError:
 import runner
 from development import normalized,write_new

def checked_source(source):
 if source.get('format')!='evaluation-source-v1':raise ValueError('Explicit evaluation-source-v1 input required')
 if source.get('schema_version','proposal-contract-v1')!='proposal-contract-v1':raise ValueError('Unsupported proposal schema')
 contexts=source.get('contexts',[]);by_context={c['id']:c for c in contexts}
 if len(contexts)!=len(by_context) or len(contexts)<2:raise ValueError('At least two distinct institutional contexts required')
 rows=source.get('items',[]);ids=set();families=defaultdict(list);texts={}
 for row in rows:
  if row['id'] in ids or row['context_id'] not in by_context:raise ValueError('Duplicate item or unknown context')
  ids.add(row['id'])
  if not row.get('tags') or not row.get('provenance',{}).get('author_id') or not isinstance(row.get('text'),str) or not row['text'].strip():raise ValueError('Text, tags and author provenance required')
  provenance=row['provenance']
  if provenance.get('kind') not in ('synthetic','consented_institutional'):raise ValueError('Explicit source kind required')
  if provenance['kind']=='consented_institutional' and not provenance.get('consent_reference'):raise ValueError('Institutional wording requires a consent reference')
  text=normalized(row['text'])
  if text in texts and texts[text]!=row['family_id']:raise ValueError('Exact duplicate wording across families')
  texts[text]=row['family_id'];families[row['family_id']].append(row)
 for family in families.values():
  if len({r['context_id'] for r in family})!=1:raise ValueError('One family cannot cross contexts')
  if len({r['language'] for r in family})!=len(family):raise ValueError('Duplicate language within family')
  if {r['language'] for r in family}!={'en','ar','arz','mixed'}:raise ValueError('Each family needs all four language categories')
 return by_context,rows,families

def wording_hash(row):
 return runner.digest({k:row[k] for k in ('id','family_id','context_id','language','text','tags','provenance')})

def plan_splits(source,seed=42,pilot_fraction=.2,development_fraction=.6):
 contexts,rows,families=checked_source(source)
 if type(seed) is not int or not 0<pilot_fraction<1 or not 0<development_fraction<1 or pilot_fraction+development_fraction>=1:raise ValueError('Positive split fractions must leave a held-out split')
 groups=defaultdict(list)
 for key,members in families.items():groups[members[0]['context_id']].append(key)
 rng=random.Random(seed);splits={'pilot':[],'development':[],'reserved':[]}
 for context,keys in sorted(groups.items()):
  keys=sorted(keys)
  if len(keys)<3:raise ValueError('Each context needs at least three families for three nonempty splits')
  rng.shuffle(keys);n=len(keys);pilot=max(1,int(n*pilot_fraction));dev=max(1,int(n*development_fraction))
  if pilot+dev>=n:dev=n-pilot-1
  if dev<1:raise ValueError('Not enough families for selected fractions')
  splits['pilot']+=keys[:pilot];splits['development']+=keys[pilot:pilot+dev];splits['reserved']+=keys[pilot+dev:]
 return {'format':'family-split-plan-v1','seed':seed,'fractions':{'pilot':pilot_fraction,'development':development_fraction,'reserved':1-pilot_fraction-development_fraction},'allocation':'whole families, stratified by context; integer counts retain at least one family per split/context','context_sha256':runner.digest([contexts[k] for k in sorted(contexts)]),'splits':{k:sorted(v) for k,v in splits.items()},'wording_sha256':{r['id']:wording_hash(r) for r in rows},'schema_version':'proposal-contract-v1','research_ready':False}

def seal(source,plan,guide,output):
 contexts,rows,families=checked_source(source)
 if not isinstance(source.get('dataset_version'),str) or not source['dataset_version'].strip():raise ValueError('Explicit release version required')
 if plan.get('format')!='family-split-plan-v1' or plan['context_sha256']!=runner.digest([contexts[k] for k in sorted(contexts)]):raise ValueError('Split plan/context mismatch')
 expected=plan_splits(source,plan['seed'],plan['fractions']['pilot'],plan['fractions']['development'])
 if expected!=plan:raise ValueError('Split membership or source wording changed after planning')
 declaration=source.get('review_declaration',{})
 protocol=declaration.get('protocol');reviewers=declaration.get('reviewer_ids',[])
 if not isinstance(reviewers,list) or not all(isinstance(r,str) and r.strip() for r in reviewers) or len(set(r.strip().casefold() for r in reviewers))!=len(reviewers):raise ValueError('Distinct declared reviewer IDs required')
 if protocol=='single_annotator':
  if len(reviewers)!=1:raise ValueError('Single-annotator protocol requires one declared reviewer')
 elif protocol=='dual_annotator_adjudicated':
  if len(reviewers)!=2 or not isinstance(declaration.get('adjudicator_id'),str) or not declaration['adjudicator_id'].strip() or declaration['adjudicator_id'].strip().casefold() in {r.strip().casefold() for r in reviewers}:raise ValueError('Dual protocol needs two reviewers and a distinct declared adjudicator')
 else:raise ValueError('Explicit reviewed annotation protocol required')
 if not declaration.get('guide_version') or not declaration.get('review_reference'):raise ValueError('Reviewed guide version and evidence reference required')
 if declaration.get('guide_sha256')!=hashlib.sha256(Path(guide).read_bytes()).hexdigest():raise ValueError('Guide does not match the recorded review hash')
 independence=source.get('independence_declaration',{})
 if independence.get('fresh_confirmatory_material') is not True or independence.get('developer_exposed_to_reserved') is not False or not independence.get('custodian_id'):raise ValueError('Fresh protected material and independent-custodian declaration required; known development material cannot become blind')
 expected_status='reviewed' if protocol=='single_annotator' else 'adjudicated'
 for row in rows:
  if row.get('review_status')!=expected_status or runner.output_errors(row.get('gold'),contexts[row['context_id']]):raise ValueError('Every item requires finalized, schema/context-valid gold for the declared review protocol')
 output=Path(output)
 if output.exists():raise FileExistsError('A sealed release cannot be overwritten')
 output.parent.mkdir(parents=True,exist_ok=True)
 temporary=Path(tempfile.mkdtemp(prefix='.evaluation-seal-',dir=output.parent))
 try:
  write_new(temporary/'contexts.json',[contexts[k] for k in sorted(contexts)])
  (temporary/'annotation-guide.md').write_bytes(Path(guide).read_bytes())
  (temporary/'proposal-contract.schema.json').write_bytes((Path(__file__).resolve().parent/'proposal-contract.schema.json').read_bytes())
  split_meta={};files={'contexts.json':None,'annotation-guide.md':None,'proposal-contract.schema.json':None}
  for split,keys in plan['splits'].items():
   selected=[{**r,'split':split} for r in sorted(rows,key=lambda r:r['id']) if r['family_id'] in keys]
   name='protected/reserved.jsonl' if split=='reserved' else split+'.jsonl'
   path=temporary/name;path.parent.mkdir(parents=True,exist_ok=True)
   path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected),encoding='utf-8');path.chmod(0o600)
   split_meta[split]={'file':name,'cases':len(selected),'families':keys,'item_hashes':{r['id']:runner.digest(r) for r in selected}}
   files[name]=None
  files={name:hashlib.sha256((temporary/name).read_bytes()).hexdigest() for name in files}
  manifest={'dataset_format':'sealed-family-release-v1','dataset_version':source.get('dataset_version','unversioned-reviewed-source'),'schema_version':plan['schema_version'],'split_plan':plan,'splits':split_meta,'files':files,'guide_version':declaration['guide_version'],'review_declaration':declaration,'independence_declaration':independence,'declaration_verification':'operator-declared; software does not verify identities, consent or blindness','independently_adjudicated':False,'reserved_is_blind':False,'technical_seal_complete':True,'research_ready':False,'limitations':['A seal establishes file/split integrity, not independent authorship or research acceptance.','Lexical and semantic leakage review remains required.','Single-annotator work must be reported with its limitation.' if protocol=='single_annotator' else 'Declared dual annotation requires external verification.']}
  write_new(temporary/'manifest.json',manifest)
  # Atomic directory publication on this filesystem; never overwrite a release.
  if output.exists():raise FileExistsError('Release already exists')
  temporary.rename(output)
 except Exception:
  shutil.rmtree(temporary,ignore_errors=True);raise
 return manifest

def load_release(root,split='development',registry=None,configuration_version=None,reason=''):
 root=Path(root);manifest=runner.read_json(root/'manifest.json')
 if manifest.get('dataset_format')!='sealed-family-release-v1' or split not in ('pilot','development','reserved'):raise ValueError('Unknown release/split')
 if split=='reserved':
  allowed=False;failure=''
  try:
   if not reason or len(reason.strip())<8 or registry is None or not configuration_version:raise ValueError('Frozen configuration and meaningful reason required')
   registry.frozen(configuration_version,manifest);allowed=True
  except (ValueError,KeyError,FileNotFoundError) as error:failure=str(error)
  with (root/'reserved-access.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'operation':'load_reserved','allowed':allowed,'reason':reason,'configuration_version':configuration_version,'manifest_sha256':runner.digest(manifest),'failure':failure})+'\n')
  if not allowed:raise ValueError(failure)
 info=manifest['splits'][split];name=info['file']
 expected_name='protected/reserved.jsonl' if split=='reserved' else split+'.jsonl'
 if name!=expected_name:raise ValueError('Invalid split path')
 for file in ('contexts.json','annotation-guide.md','proposal-contract.schema.json',name):
  if hashlib.sha256((root/file).read_bytes()).hexdigest()!=manifest['files'][file]:raise ValueError('Sealed file hash mismatch')
 contexts={c['id']:c for c in runner.read_json(root/'contexts.json')};rows=runner.read_rows(root/name)
 if len(rows)!=info['cases'] or {r['family_id'] for r in rows}!=set(info['families']) or len({r['id'] for r in rows})!=len(rows) or {r['id']:runner.digest(r) for r in rows}!=info['item_hashes']:raise ValueError('Sealed item membership/hash mismatch')
 if any(r.get('split')!=split or runner.output_errors(r['gold'],contexts[r['context_id']]) for r in rows):raise ValueError('Invalid sealed annotation')
 return manifest,contexts,rows

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['plan','seal','validate-development']);p.add_argument('--source',type=Path);p.add_argument('--plan',type=Path);p.add_argument('--guide',type=Path);p.add_argument('--output',type=Path);p.add_argument('--release',type=Path);p.add_argument('--seed',type=int,default=42);p.add_argument('--pilot-fraction',type=float,default=.2);p.add_argument('--development-fraction',type=float,default=.6);args=p.parse_args()
 if args.command=='validate-development':
  if not args.release:p.error('--release required')
  manifest,contexts,rows=load_release(args.release);print(json.dumps({'cases':len(rows),'contexts':len(contexts),'research_ready':False}));return
 if not args.source or not args.output:p.error('--source and --output required')
 source=runner.read_json(args.source)
 if args.command=='plan':write_new(args.output,plan_splits(source,args.seed,args.pilot_fraction,args.development_fraction))
 else:
  if not args.plan or not args.guide:p.error('--plan and --guide required')
  seal(source,runner.read_json(args.plan),args.guide,args.output)
 print('Saved technical artifact; human-review and independence declarations are not certified.')
if __name__=='__main__':main()
