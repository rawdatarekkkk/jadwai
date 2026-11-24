"""Derive development bundle 0.2.1-draft from 0.2.0-draft by merging synonymous codes.

Guide v2.1 (24 November 2026) retires two codes that duplicated existing ones.
Only gold clarification/unsupported codes change; wording, contexts, decisions and
proposals are copied unchanged. Bundle 0.2.0-draft is read through its integrity
check and left as it is. Reserved material is never read.
"""
import copy,hashlib,json,shutil
from pathlib import Path
import development,runner
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'development-v2'
OUT=ROOT/'development-v2.1'
GUIDE_VERSION='annotation-guide-v2.1-draft'
RENAMES={
 'clarifications':{'missing_day':'day_required'},
 'unsupported':{'minute_rule_precision':'manual_rule_minute_precision_not_supported'},
}

def merged(gold):
 gold=copy.deepcopy(gold)
 for field,renames in RENAMES.items():
  codes=[]
  for code in gold[field]:
   code=renames.get(code,code)
   if code not in codes:codes.append(code)
  gold[field]=codes
 return gold

def build():
 previous,contexts,rows=development.load_bundle(SOURCE)
 changed=[]
 for row in rows:
  gold=merged(row['gold'])
  if gold!=row['gold']:changed.append(row['id']);row['gold']=gold
  if runner.output_errors(row['gold'],contexts[row['context_id']]):raise ValueError('Invalid gold: '+row['id'])
 guide=development.bundle_guide({'guide_version':GUIDE_VERSION})
 OUT.mkdir(exist_ok=False)
 shutil.copyfile(SOURCE/'contexts.json',OUT/'contexts.json')
 with (OUT/'cases.jsonl').open('x',encoding='utf-8') as stream:stream.write(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
 manifest={'dataset_format':'development-bundle-v1','dataset_version':'0.2.1-draft','previous_manifest_sha256':runner.digest(previous),'schema_version':previous['schema_version'],'guide_version':GUIDE_VERSION,'split':'development','counts':previous['counts'],'independently_adjudicated':False,'reserved_is_blind':False,'reserved_included':False,
  'files':{name:digest(OUT/name) for name in ('contexts.json','cases.jsonl')},'contract_sha256':previous['contract_sha256'],'guide_sha256':digest(guide),
  'code_renames':RENAMES,'changed_item_ids':changed,
  'change_note':'Guide v2.1 (24 November 2026): merge synonymous codes missing_day -> day_required and minute_rule_precision -> manual_rule_minute_precision_not_supported. Gold codes only; statements, contexts, decisions and proposals unchanged from 0.2.0-draft. Results reported before this date were scored on 0.2.0-draft labels. No reserved labels loaded or moved.'}
 with (OUT/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2)
 development.load_bundle(OUT)
 print(json.dumps({'changed':len(changed),**manifest['counts']}))
if __name__=='__main__':build()
