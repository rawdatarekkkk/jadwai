"""Phase 5 extensions. Offline only; the original manifest and corpus stay intact."""
import argparse
from collections import defaultdict
from datetime import datetime,timezone
import hashlib,json,math,random,re
from pathlib import Path
try:
 from . import runner as base
except ImportError:
 import runner as base

def write_new(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)

def token(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}',value):raise ValueError('Invalid version identifier')
 return value

def validate_configuration(config,manifest):
 for key in ('provider','model','schema_version','prompt_version','fewshot_version'):
  value=config.get(key)
  if not isinstance(value,str) or not value.strip() or value in ('not_selected','not_frozen'):raise ValueError('Complete configuration required: '+key)
 if config['schema_version']!=manifest['schema_version']:raise ValueError('Schema mismatch')
 if not isinstance(config.get('decoding'),dict) or not config['decoding']:raise ValueError('Explicit decoding settings required')
 for key in ('retry_limit','repetitions'):
  if type(config.get(key)) is not int or config[key]<(1 if key=='repetitions' else 0):raise ValueError('Explicit retry/repetition settings required')
 timeout=config.get('timeout_seconds')
 if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0:raise ValueError('Positive timeout required')

class Registry:
 """Append-only local files; hashes detect edits, not an OS security boundary."""
 def __init__(self,root):self.root=Path(root)
 def path(self,kind,version):return self.root/token(kind)/(token(version)+'.json')
 def register(self,kind,version,content,note,purpose='development'):
  if kind not in ('prompt','fewshot','configuration'):raise ValueError('Unknown artifact kind')
  if purpose not in ('development','confirmatory') or not note.strip():raise ValueError('Purpose and change note required')
  document={'kind':kind,'version':version,'content':content,'note':note,'purpose':purpose,'created_at':datetime.now(timezone.utc).isoformat()}
  document['sha256']=base.digest(document)
  write_new(self.path(kind,version),document)
  return document
 def read(self,kind,version):
  document=base.read_json(self.path(kind,version));expected=document.pop('sha256')
  if base.digest(document)!=expected:raise ValueError('Versioned artifact was modified')
  document['sha256']=expected
  if document['kind']!=kind or document['version']!=version:raise ValueError('Artifact identity mismatch')
  return document
 def freeze(self,version,config,note,manifest):
  validate_configuration(config,manifest)
  refs={}
  for kind in ('prompt','fewshot'):
   artifact=self.read(kind,config[kind+'_version'])
   if artifact['purpose']!='confirmatory':raise ValueError('Development artifacts cannot authorize reserved scoring')
   refs[kind]=artifact['sha256']
  content={'configuration':config,'artifact_hashes':refs,'manifest_sha256':base.digest(manifest)}
  return self.register('configuration',version,content,note,'confirmatory')
 def frozen(self,version,manifest):
  record=self.read('configuration',version);content=record['content']
  if record['purpose']!='confirmatory' or content['manifest_sha256']!=base.digest(manifest):raise ValueError('Frozen configuration or manifest mismatch')
  validate_configuration(content['configuration'],manifest)
  if set(content['artifact_hashes'])!={'prompt','fewshot'}:raise ValueError('Both frozen dependencies are required')
  for kind,expected in content['artifact_hashes'].items():
   artifact=self.read(kind,content['configuration'][kind+'_version'])
   if artifact['sha256']!=expected or artifact['purpose']!='confirmatory':raise ValueError('Frozen dependency mismatch')
  return record

def guarded_load(root,mode='development',registry=None,configuration_version=None,reason=''):
 root=Path(root)
 if mode=='development':
  manifest=base.read_json(root/'manifest.json')
  if manifest.get('dataset_format')=='sealed-family-release-v1':
   try:
    from .dataset_lifecycle import load_release
   except ImportError:
    from dataset_lifecycle import load_release
   return load_release(root)
  if manifest.get('dataset_format')=='development-bundle-v1':
   try:
    from .development import load_bundle
   except ImportError:
    from development import load_bundle
   return load_bundle(root)
  return base.load(root)
 if mode!='reserved':raise ValueError('Unknown experiment mode')
 manifest=base.read_json(root/'manifest.json')
 if manifest.get('dataset_format')=='sealed-family-release-v1':
  try:
   from .dataset_lifecycle import load_release
  except ImportError:
   from dataset_lifecycle import load_release
  return load_release(root,'reserved',registry,configuration_version,reason)
 allowed=False;failure=''
 try:
  if manifest.get('dataset_format')=='development-bundle-v1':raise ValueError('Development-only bundles have no reserved scoring path')
  if not reason or len(reason.strip())<8:raise ValueError('Meaningful access reason required')
  if registry is None or not configuration_version:raise ValueError('Frozen configuration required')
  registry.frozen(configuration_version,manifest)
  allowed=True
 except (ValueError,KeyError,FileNotFoundError) as error:failure=str(error)
 with (root/'guard-access-log.jsonl').open('a',encoding='utf-8') as stream:
  stream.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'mode':mode,'allowed':allowed,'reason':reason,'configuration_version':configuration_version,'failure':failure,'manifest_sha256':base.digest(manifest)})+'\n')
 if not allowed:raise ValueError(failure)
 return base.load(root,'reserved',True,reason,'guarded-score')

def percentile(values,p):
 if not values:return None
 values=sorted(values);index=(len(values)-1)*p;low=math.floor(index);high=math.ceil(index)
 return values[low]+(values[high]-values[low])*(index-low)

def clustered_score(rows,contexts,predictions,stage='raw',replicates=1000,seed=42):
 if type(replicates) is not int or replicates<100 or replicates>10000:raise ValueError('Use 100–10000 bootstrap replicates')
 result=base.score(rows,contexts,predictions,stage)
 families=defaultdict(list)
 for row in rows:families[row['family_id']].append(row)
 prediction_map={p['id']:p for p in predictions}
 blocks=[base.score(members,contexts,[prediction_map[r['id']] for r in members if r['id'] in prediction_map],stage) for members in families.values()]
 rng=random.Random(seed);draws=defaultdict(list)
 for _ in range(replicates):
  sample=rng.choices(blocks,k=len(blocks)) if blocks else []
  count=sum(b['case_count'] for b in sample)
  measures={'end_to_end_accuracy':base.ratio(sum(b['exact_cases'] for b in sample),count),'decision_accuracy':base.ratio(sum(b['decision_accuracy']*b['case_count'] for b in sample),count) if count else None}
  for name in result['metrics']:
   aggregate={k:sum(b['metrics'][name][k] for b in sample) for k in ('true_positive','predicted','expected')}
   metric=base.metrics(aggregate['true_positive'],aggregate['predicted'],aggregate['expected'])
   for field in ('precision','recall','f1'):measures[name+'.'+field]=metric[field]
  for name,value in measures.items():
   if value is not None:draws[name].append(value)
 estimates={'end_to_end_accuracy':result['end_to_end_accuracy'],'decision_accuracy':result['decision_accuracy']}
 estimates.update({name+'.'+field:value[field] for name,value in result['metrics'].items() for field in ('precision','recall','f1')})
 result['uncertainty']={'method':'percentile bootstrap resampling entire intent families with replacement','confidence':0.95,'replicates':replicates,'seed':seed,'family_count':len(blocks),'intervals':{name:{'estimate':estimate,'lower':percentile(draws[name],.025) if len(blocks)>=2 else None,'upper':percentile(draws[name],.975) if len(blocks)>=2 else None,'defined_replicates':len(draws[name])} for name,estimate in estimates.items()},'limitations':'Synthetic draft families are not a representative institutional sample. Degenerate intervals at 0/1 do not establish certainty. Undefined classes stay null; fewer than two families have no interval.'}
 return result

def agreement(left,right):
 if set(left)!=set(right) or not left:raise ValueError('Reviewers must label the same nonempty item set')
 from collections import Counter
 n=len(left);a=Counter(left.values());b=Counter(right.values())
 observed=sum(left[k]==right[k] for k in left)/n
 chance=sum(a[c]*b[c] for c in set(a)|set(b))/(n*n)
 return {'items':n,'raw_agreement':observed,'cohen_kappa':(observed-chance)/(1-chance) if chance<1 else None}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['register','freeze','score']);p.add_argument('--dataset',type=Path,default=base.ROOT);p.add_argument('--registry',type=Path,default=base.ROOT/'versions');p.add_argument('--version');p.add_argument('--kind',choices=['prompt','fewshot']);p.add_argument('--purpose',choices=['development','confirmatory'],default='development');p.add_argument('--note',default='');p.add_argument('--file',type=Path);p.add_argument('--mode',choices=['development','reserved'],default='development');p.add_argument('--reason',default='');p.add_argument('--predictions',type=Path);p.add_argument('--output',type=Path);p.add_argument('--stage',choices=['raw','post_review'],default='raw');args=p.parse_args();registry=Registry(args.registry)
 if args.command=='register':
  if not args.file or not args.kind or not args.version:p.error('register requires --file, --kind, --version and --note')
  registry.register(args.kind,args.version,args.file.read_text(),args.note,args.purpose);return
 if args.command=='freeze':
  if not args.file or not args.version:p.error('freeze requires --file, --version and --note')
  registry.freeze(args.version,base.read_json(args.file),args.note,base.read_json(args.dataset/'manifest.json'));return
 if not args.predictions or not args.output:p.error('score requires --predictions and --output')
 manifest,contexts,rows=guarded_load(args.dataset,args.mode,registry,args.version,args.reason)
 configuration=registry.frozen(args.version,manifest) if args.mode=='reserved' else None
 if args.mode=='development':
  if not args.file:p.error('Development scoring requires --file with the actual run configuration')
  development_config=base.read_json(args.file)
  for key in ('provider','model','prompt_version','schema_version'):
   if not isinstance(development_config.get(key),str) or development_config[key] in ('','not_selected','not_frozen'):p.error('Actual run configuration required: '+key)
  configuration={'content':development_config,'sha256':base.digest(development_config)}
 result=clustered_score(rows,contexts,base.read_rows(args.predictions),args.stage)
 result['configuration']=configuration
 result.update(dataset_version=manifest['dataset_version'],manifest_sha256=base.digest(manifest),predictions_sha256=hashlib.sha256(args.predictions.read_bytes()).hexdigest(),harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),configuration_version=args.version,configuration_sha256=configuration['sha256'],created_at=datetime.now(timezone.utc).isoformat(),reserved_is_blind=False,independently_adjudicated=False)
 resolved=args.output.resolve()
 if resolved.is_relative_to(base.ROOT.resolve()):p.error('Write scoring reports outside the evaluation source directory')
 write_new(args.output,result)
 print('Saved offline diagnostics; no provider calls were made.')

if __name__=='__main__':main()
