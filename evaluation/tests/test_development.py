import copy,hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import development as dev
import harness
ROOT=Path(__file__).resolve().parents[1]
class DevelopmentTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def test_release_has_two_contexts_and_no_reserved_data(self):
  manifest,contexts,rows=dev.load_bundle(ROOT/'development-v2')
  self.assertEqual(manifest['counts'],{'cases':144,'families':36,'contexts':2})
  self.assertEqual(len(contexts),2)
  self.assertTrue(all(r['split']=='development' for r in rows))
  self.assertTrue(all(r['tags'] and r['provenance'] for r in rows))
  self.assertEqual(len(harness.guarded_load(ROOT/'development-v2')[2]),144)
 def test_gold_free_review_keeps_full_families_and_is_reproducible(self):
  pack=dev.review_pack(ROOT/'development-v2',6,42)
  self.assertEqual(pack,dev.review_pack(ROOT/'development-v2',6,42))
  self.assertEqual(len(pack['items']),24)
  self.assertTrue(all(item['annotation'] is None and 'gold' not in item for item in pack['items']))
  self.assertNotIn('expected',json.dumps(pack))
 def annotated(self):
  pack=dev.review_pack(ROOT/'development-v2',2,42);annotated=copy.deepcopy(pack)
  by_id={r['id']:r for r in dev.load_bundle(ROOT/'development-v2')[2]}
  for item in annotated['items']:
   item['annotation']=copy.deepcopy(by_id[item['id']]['gold']);item['rationale']='Synthetic test fixture only, not human review.'
  return pack,annotated
 def test_review_import_requires_complete_and_valid_source_annotations(self):
  pack,annotated=self.annotated();record=dev.import_review(ROOT/'development-v2',pack,annotated,'unit-reviewer')
  self.assertFalse(record['adjudicated']);self.assertEqual(record['reviewer_identity_verification'],'operator_declared_only')
  for corruption in ('missing','duplicate','changed_text','invalid','blank_rationale'):
   bad=copy.deepcopy(annotated)
   if corruption=='missing':bad['items'].pop()
   elif corruption=='duplicate':bad['items'].append(bad['items'][0])
   elif corruption=='changed_text':bad['items'][0]['text']='Different requirement'
   elif corruption=='invalid':bad['items'][0]['annotation']=None
   else:bad['items'][0]['rationale']=''
   with self.assertRaises(ValueError):dev.import_review(ROOT/'development-v2',pack,bad,'unit-reviewer')
 def test_agreement_requires_distinct_reviewers_and_same_pack(self):
  pack,annotated=self.annotated();a=dev.import_review(ROOT/'development-v2',pack,annotated,'test-a');b=dev.import_review(ROOT/'development-v2',pack,annotated,'test-b')
  result=dev.compare_reviews(a,b)
  self.assertEqual(result['decision_agreement']['raw_agreement'],1)
  self.assertFalse(result['semantic_agreement']['disagreement_ids'])
  with self.assertRaises(ValueError):dev.compare_reviews(a,a)
  b['review_pack_sha256']='other'
  with self.assertRaises(ValueError):dev.compare_reviews(a,b)
 def test_release_tampering_is_detected(self):
  root=self.path/'release';shutil.copytree(ROOT/'development-v2',root)
  with (root/'cases.jsonl').open('a') as out:out.write('\n')
  with self.assertRaises(ValueError):dev.load_bundle(root)
 def test_lexical_screen_flags_without_disclosing_reference_details(self):
  text='The studio closes on Tuesday';normalized=dev.normalized(text)
  reference={'format':'leakage-fingerprints-v1','families':[{'exact_hashes':[hashlib.sha256(normalized.encode()).hexdigest()],'shingle_hashes':[]}]}
  result=dev.screen_fingerprints([{'id':'candidate','text':text},{'id':'unrelated','text':'Completely different text'}],reference)
  self.assertEqual(result['flags'],[{'id':'candidate','flagged':True}])
  self.assertNotIn('The studio',json.dumps(result))
 def test_review_output_cannot_overwrite_a_prior_review(self):
  dev.write_new(self.path/'review.json',{'test':True})
  with self.assertRaises(FileExistsError):dev.write_new(self.path/'review.json',{'test':False})
 def test_reserved_request_on_development_bundle_is_denied_and_logged(self):
  root=self.path/'release';shutil.copytree(ROOT/'development-v2',root)
  with self.assertRaises(ValueError):harness.guarded_load(root,'reserved',reason='Unit test invalid reserved request')
  self.assertFalse(json.loads((root/'guard-access-log.jsonl').read_text())['allowed'])
 def test_harness_cli_scores_new_bundle_as_explicit_software_check(self):
  import subprocess
  predictions=self.path/'empty.jsonl';predictions.write_text('')
  config=self.path/'config.json';config.write_text(json.dumps({'provider':'software-check','model':'no-model-called','prompt_version':'none-software-check','schema_version':'proposal-contract-v1'}))
  result=self.path/'score.json'
  command=[sys.executable,str(ROOT/'harness.py'),'score','--dataset',str(ROOT/'development-v2'),'--mode','development','--predictions',str(predictions),'--file',str(config),'--output',str(result)]
  run=subprocess.run(command,capture_output=True,text=True)
  self.assertEqual(run.returncode,0,run.stderr)
  report=json.loads(result.read_text())
  self.assertEqual(report['case_count'],144)
  self.assertEqual(report['missing_predictions'],144)
  self.assertEqual(report['uncertainty']['family_count'],36)
  self.assertTrue(report['configuration_sha256'])
  self.assertFalse(report['independently_adjudicated'])
 def test_adjudication_records_corrections_without_overwriting_gold(self):
  pack,annotated=self.annotated();a=dev.import_review(ROOT/'development-v2',pack,annotated,'test-a')
  alternate=copy.deepcopy(annotated)
  alternate['items'][0]['annotation']={'decision':'clarify','proposals':[],'clarifications':['unit-test-disagreement'],'unsupported':[]}
  b=dev.import_review(ROOT/'development-v2',pack,alternate,'test-b')
  with self.assertRaises(ValueError):dev.adjudicate(ROOT/'development-v2',a,b,[],'test-adjudicator')
  resolution={'id':pack['items'][0]['id'],'annotation':alternate['items'][0]['annotation'],'rationale':'Synthetic disagreement resolution to test record keeping.'}
  record=dev.adjudicate(ROOT/'development-v2',a,b,[resolution],'test-adjudicator')
  self.assertFalse(record['release_promoted'])
  changed=next(d for d in record['decisions'] if d['id']==resolution['id'])
  self.assertFalse(changed['matches_original_draft'])
  self.assertNotEqual(changed['draft_gold_sha256'],changed['adjudicated_annotation_sha256'])
  self.assertEqual(dev.load_bundle(ROOT/'development-v2')[0]['counts']['cases'],144)
