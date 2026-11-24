"""Validate development-only bundles and preserve independent annotation records."""
import argparse,hashlib,json,random,unicodedata
from pathlib import Path
try:
 from . import runner
except ImportError:
 import runner

def digest_file(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def normalized(text):return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())
def write_new(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)

GUIDE_FILES={'annotation-guide-v2-draft':'guides/annotation-guide-v2.md','annotation-guide-v2.1-draft':'guides/annotation-guide-v2.1.md'}
def bundle_guide(manifest):
 """Guide file whose hash a bundle manifest records, chosen by its guide_version."""
 name=GUIDE_FILES.get(manifest.get('guide_version'))
 if name is None:raise ValueError('Unknown guide version: '+str(manifest.get('guide_version')))
 return Path(__file__).resolve().parent/name

def load_bundle(root):
 root=Path(root);manifest=runner.read_json(root/'manifest.json')
 if manifest.get('dataset_format')!='development-bundle-v1' or manifest.get('split')!='development' or manifest.get('reserved_included') is not False:raise ValueError('Not a development-only bundle')
 if set(manifest['files'])!={'contexts.json','cases.jsonl'}:raise ValueError('Unexpected bundle file set')
 for name,expected in manifest['files'].items():
  if digest_file(root/name)!=expected:raise ValueError('Bundle file integrity mismatch: '+name)
 source=Path(__file__).resolve().parent
 if digest_file(source/'proposal-contract.schema.json')!=manifest['contract_sha256'] or digest_file(bundle_guide(manifest))!=manifest['guide_sha256']:raise ValueError('Guide or contract changed; create a new release')
 contexts=runner.read_json(root/'contexts.json');contexts={c['id']:c for c in contexts};rows=runner.read_rows(root/'cases.jsonl')
 ids=set();family_context={};family_languages={};text_families={}
 for row in rows:
  if row['id'] in ids or row['split']!='development':raise ValueError('Duplicate ID or split leakage')
  ids.add(row['id'])
  if not row.get('tags') or not row.get('provenance') or row.get('review_status')!='draft_unreviewed':raise ValueError('Missing draft provenance')
  family=row['family_id'];context=row['context_id']
  if family in family_context and family_context[family]!=context:raise ValueError('Family crosses contexts')
  family_context[family]=context
  languages=family_languages.setdefault(family,set())
  if row['language'] in languages:raise ValueError('Duplicate family/language')
  languages.add(row['language'])
  if context not in contexts or runner.output_errors(row['gold'],contexts[context]):raise ValueError('Invalid gold: '+row['id'])
  text=normalized(row['text'])
  if text in text_families and text_families[text]!=family:raise ValueError('Exact duplicate text across families')
  text_families[text]=family
 if any(languages!={'en','ar','arz','mixed'} for languages in family_languages.values()):raise ValueError('Incomplete language family')
 actual={'cases':len(rows),'families':len(family_context),'contexts':len(contexts)}
 if actual!=manifest['counts']:raise ValueError('Bundle count mismatch')
 return manifest,contexts,rows

def review_pack(root,families=4,seed=42):
 manifest,contexts,rows=load_bundle(root)
 available=sorted({r['family_id'] for r in rows})
 if type(families) is not int or not 1<=families<=len(available):raise ValueError('Invalid family count')
 selected=set(random.Random(seed).sample(available,families));selected_rows=[r for r in rows if r['family_id'] in selected]
 return {'format':'gold-free-review-v1','manifest_sha256':runner.digest(manifest),'guide_version':manifest['guide_version'],'sampling':{'unit':'whole intent family','families':sorted(selected),'seed':seed},'contexts':[contexts[k] for k in sorted({r['context_id'] for r in selected_rows})],'items':[{**{key:r[key] for key in ('id','text','context_id','language')},'annotation':None,'rationale':''} for r in selected_rows]}

def import_review(root,pack,annotated,reviewer):
 if not isinstance(reviewer,str) or not reviewer.strip():raise ValueError('Pseudonymous reviewer ID required')
 manifest,contexts,rows=load_bundle(root);source={r['id']:r for r in rows}
 if pack.get('format')!='gold-free-review-v1' or pack['manifest_sha256']!=runner.digest(manifest):raise ValueError('Review pack/version mismatch')
 if annotated.get('format')!=pack['format'] or annotated['manifest_sha256']!=pack['manifest_sha256']:raise ValueError('Annotated version mismatch')
 expected={r['id']:r for r in pack['items']}
 if len(expected)!=len(pack['items']) or not expected or not set(expected)<=set(source):raise ValueError('Invalid review scope')
 seen=set();annotations=[]
 for item in annotated['items']:
  ident=item['id']
  if ident in seen or ident not in expected:raise ValueError('Duplicate or unknown reviewed item')
  seen.add(ident)
  for key in ('text','context_id','language'):
   if item.get(key)!=source[ident][key] or expected[ident].get(key)!=source[ident][key]:raise ValueError('Review source text/context changed')
  errors=runner.output_errors(item.get('annotation'),contexts[source[ident]['context_id']])
  if errors:raise ValueError('Invalid annotation for '+ident+': '+','.join(errors))
  if not isinstance(item.get('rationale'),str) or not item['rationale'].strip():raise ValueError('Rationale required for '+ident)
  annotations.append({'id':ident,'annotation':item['annotation'],'rationale':item['rationale']})
 if seen!=set(expected):raise ValueError('Review is incomplete')
 return {'format':'annotation-review-v1','reviewer_id':reviewer.strip(),'reviewer_identity_verification':'operator_declared_only','manifest_sha256':runner.digest(manifest),'review_pack_sha256':runner.digest(pack),'guide_version':manifest['guide_version'],'annotations':annotations,'adjudicated':False}

def compare_reviews(first,second):
 try:
  from .harness import agreement
 except ImportError:
  from harness import agreement
 if first.get('format')!='annotation-review-v1' or second.get('format')!=first['format'] or first['manifest_sha256']!=second['manifest_sha256'] or first['review_pack_sha256']!=second['review_pack_sha256']:raise ValueError('Reviews must use the same dataset and pack')
 if first['reviewer_id']==second['reviewer_id']:raise ValueError('Two distinct declared reviewers required')
 left={r['id']:r['annotation'] for r in first['annotations']};right={r['id']:r['annotation'] for r in second['annotations']}
 if set(left)!=set(right) or not left:raise ValueError('Reviews have different item scopes')
 decisions=agreement({k:v['decision'] for k,v in left.items()},{k:v['decision'] for k,v in right.items()})
 disagreements=[ident for ident in left if not runner.semantic_equal(left[ident],right[ident])]
 return {'manifest_sha256':first['manifest_sha256'],'reviewer_ids':[first['reviewer_id'],second['reviewer_id']],'review_record_sha256':[runner.digest(first),runner.digest(second)],'decision_agreement':decisions,'semantic_agreement':{'items':len(left),'equal':len(left)-len(disagreements),'disagreement_ids':disagreements},'adjudicated':False,'identity_note':'Reviewer names and independence are operator-declared, not verified by the software.'}

def adjudicate(root,first,second,resolutions,adjudicator):
 comparison=compare_reviews(first,second)
 if not isinstance(adjudicator,str) or not adjudicator.strip():raise ValueError('Adjudicator ID required')
 manifest,contexts,rows=load_bundle(root);source={r['id']:r for r in rows}
 if first['manifest_sha256']!=runner.digest(manifest):raise ValueError('Adjudication bundle mismatch')
 left={r['id']:r['annotation'] for r in first['annotations']};right={r['id']:r['annotation'] for r in second['annotations']}
 for ident in left:
  if ident not in source or runner.output_errors(left[ident],contexts[source[ident]['context_id']]) or runner.output_errors(right[ident],contexts[source[ident]['context_id']]):raise ValueError('Invalid reviewed annotation')
 resolved={r['id']:r for r in resolutions}
 if len(resolved)!=len(resolutions) or set(resolved)!=set(comparison['semantic_agreement']['disagreement_ids']):raise ValueError('Resolve every disagreement exactly once; do not override agreed items')
 decisions=[]
 for ident in left:
  item=resolved.get(ident)
  annotation=item['annotation'] if item else left[ident]
  reason=item.get('rationale') if item else 'Both declared reviewers supplied semantically equal annotations.'
  if not isinstance(reason,str) or not reason.strip():raise ValueError('Resolution rationale required')
  if runner.output_errors(annotation,contexts[source[ident]['context_id']]):raise ValueError('Invalid adjudicated annotation')
  decisions.append({'id':ident,'annotation':annotation,'rationale':reason,'draft_gold_sha256':runner.digest(source[ident]['gold']),'adjudicated_annotation_sha256':runner.digest(annotation),'matches_original_draft':runner.semantic_equal(source[ident]['gold'],annotation)})
 return {'format':'annotation-adjudication-v1','manifest_sha256':runner.digest(manifest),'review_record_sha256':[runner.digest(first),runner.digest(second)],'adjudicator_id':adjudicator.strip(),'identity_verification':'operator_declared_only','guide_version':manifest['guide_version'],'decisions':decisions,'release_promoted':False,'note':'This record preserves declared decisions. It does not edit gold or certify reviewer independence.'}

def screen_fingerprints(rows,reference,threshold=.65):
 """Flags only; no reference text/IDs returned. Does not certify semantic isolation."""
 if reference.get('format')!='leakage-fingerprints-v1':raise ValueError('Unknown fingerprint format')
 if not 0<threshold<=1:raise ValueError('Invalid similarity threshold')
 flags=[];families=reference['families']
 for row in rows:
  text=normalized(row['text']);words=text.split();shingles={' '.join(words[i:i+3]) for i in range(max(0,len(words)-2))}
  hashes={hashlib.sha256(s.encode()).hexdigest() for s in shingles};exact=hashlib.sha256(text.encode()).hexdigest()
  for family in families:
   other=set(family['shingle_hashes'])
   score=len(hashes&other)/len(hashes|other) if hashes or other else 0
   if exact in family['exact_hashes'] or score>=threshold:
    flags.append({'id':row['id'],'flagged':True});break
 return {'flags':flags,'threshold':threshold,'method':'exact normalized hash or token-trigram Jaccard','reference_sha256':runner.digest(reference),'limitations':'Lexical screen only; unflagged translations or paraphrases can still leak semantics.'}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['validate','export-review','import-review','compare','adjudicate','screen']);parser.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parent/'development-v2');parser.add_argument('--output',type=Path);parser.add_argument('--families',type=int,default=4);parser.add_argument('--seed',type=int,default=42);parser.add_argument('--pack',type=Path);parser.add_argument('--annotations',type=Path);parser.add_argument('--reviewer');parser.add_argument('--first',type=Path);parser.add_argument('--second',type=Path);parser.add_argument('--resolutions',type=Path);parser.add_argument('--fingerprints',type=Path);args=parser.parse_args()
 if args.command=='validate':print(json.dumps(load_bundle(args.bundle)[0]['counts']));return
 if not args.output:parser.error('--output required')
 if args.output.resolve().is_relative_to(args.bundle.resolve()):parser.error('Review outputs cannot overwrite release files')
 if args.command=='export-review':result=review_pack(args.bundle,args.families,args.seed)
 elif args.command=='import-review':
  if not args.pack or not args.annotations or not args.reviewer:parser.error('--pack, --annotations and --reviewer required')
  result=import_review(args.bundle,runner.read_json(args.pack),runner.read_json(args.annotations),args.reviewer)
 elif args.command=='adjudicate':
  if not args.first or not args.second or not args.resolutions or not args.reviewer:parser.error('--first, --second, --resolutions and --reviewer (adjudicator ID) required')
  result=adjudicate(args.bundle,runner.read_json(args.first),runner.read_json(args.second),runner.read_json(args.resolutions),args.reviewer)
 elif args.command=='compare':
  if not args.first or not args.second:parser.error('--first and --second required')
  result=compare_reviews(runner.read_json(args.first),runner.read_json(args.second))
 else:
  if not args.fingerprints:parser.error('--fingerprints required; prepare independently from protected material')
  result=screen_fingerprints(load_bundle(args.bundle)[2],runner.read_json(args.fingerprints))
 write_new(args.output,result)
 print('Saved '+args.command+' output; dataset labels are unchanged.')
if __name__=='__main__':main()
