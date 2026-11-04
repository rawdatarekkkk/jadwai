"""Synthetic software fixtures only; never create a real confirmatory release."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dataset_lifecycle as lifecycle
import harness

class DatasetLifecycleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.guide=self.root/'guide.md';self.guide.write_text('Unit-test guide only; not reviewed research material.')
  contexts=[];rows=[]
  for name in ('context-a','context-b'):
   context={'id':name,'calendar':{'days':['Monday'],'start_hour':8,'end_hour':18},'instructors':[],'rooms':[{'id':name+'-room','name':'Synthetic room'}],'groups':[],'activities':[]}
   contexts.append(context)
   for family in range(3):
    for lang in ('en','ar','arz','mixed'):
     rows.append({'id':f'{name}-{family}-{lang}','family_id':f'{name}-family-{family}','context_id':name,'language':lang,'text':f'Unit fixture only {name} family {family} language {lang}','tags':['unit-fixture'],'provenance':{'author_id':'unit-test-not-a-real-author','kind':'synthetic'},'review_status':'reviewed','gold':{'decision':'ready','proposals':[{'kind':'rule','data':{'type':'room_unavailable','room_id':name+'-room','day':'Monday','start_hour':8,'end_hour':10,'strength':'mandatory'}}],'clarifications':[],'unsupported':[]}})
  self.source={'format':'evaluation-source-v1','dataset_version':'unit-test-only','contexts':contexts,'items':rows,'review_declaration':{'protocol':'single_annotator','reviewer_ids':['unit-reviewer'],'guide_version':'unit-guide','guide_sha256':hashlib.sha256(self.guide.read_bytes()).hexdigest(),'review_reference':'Unit test fixture; no human annotation claimed'},'independence_declaration':{'fresh_confirmatory_material':True,'developer_exposed_to_reserved':False,'custodian_id':'unit-custodian'}}
 def tearDown(self):self.temp.cleanup()
 def seal(self):
  plan=lifecycle.plan_splits(self.source);output=self.root/'release'
  manifest=lifecycle.seal(self.source,plan,self.guide,output)
  return output,manifest
 def registry(self,manifest):
  registry=harness.Registry(self.root/'versions')
  for kind in ('prompt','fewshot'):registry.register(kind,'test','Unit-test material, not a model prompt.','Unit test only','confirmatory')
  registry.freeze('test',{'provider':'unit-double','model':'no-real-model','schema_version':manifest['schema_version'],'prompt_version':'test','fewshot_version':'test','decoding':{'temperature':0},'retry_limit':0,'repetitions':1,'timeout_seconds':10},'Unit test only',manifest)
  return registry
 def test_family_splits_are_reproducible_disjoint_and_context_stratified(self):
  plan=lifecycle.plan_splits(self.source)
  self.assertEqual(plan,lifecycle.plan_splits(self.source))
  reordered=copy.deepcopy(self.source);reordered['items'].reverse();reordered['contexts'].reverse()
  self.assertEqual(plan,lifecycle.plan_splits(reordered))
  sets=[set(plan['splits'][s]) for s in ('pilot','development','reserved')]
  self.assertEqual(len(set.union(*sets)),6)
  self.assertTrue(all(not a&b for i,a in enumerate(sets) for b in sets[i+1:]))
  self.assertTrue(all(len(s)==2 for s in sets))
 def test_single_admin_protocol_is_explicit_and_never_certifies_independence(self):
  output,manifest=self.seal()
  self.assertEqual(manifest['review_declaration']['protocol'],'single_annotator')
  self.assertTrue(manifest['technical_seal_complete'])
  self.assertFalse(manifest['research_ready']);self.assertFalse(manifest['independently_adjudicated']);self.assertFalse(manifest['reserved_is_blind'])
  self.assertTrue(any('Single-annotator' in x for x in manifest['limitations']))
  with self.assertRaises(FileExistsError):lifecycle.seal(self.source,lifecycle.plan_splits(self.source),self.guide,output)
 def test_changed_wording_or_split_cannot_be_sealed_under_old_plan(self):
  plan=lifecycle.plan_splits(self.source);changed=copy.deepcopy(self.source);changed['items'][0]['text']='Changed after planning'
  with self.assertRaises(ValueError):lifecycle.seal(changed,plan,self.guide,self.root/'bad')
  plan['splits']['reserved']=plan['splits']['development']
  with self.assertRaises(ValueError):lifecycle.seal(self.source,plan,self.guide,self.root/'bad')
 def test_unreviewed_or_known_exposed_data_cannot_be_sealed(self):
  for field in ('unreviewed','exposed','guide','protocol'):
   source=copy.deepcopy(self.source)
   if field=='unreviewed':source['items'][0]['review_status']='draft_unreviewed'
   elif field=='exposed':source['independence_declaration']['developer_exposed_to_reserved']=True
   elif field=='guide':source['review_declaration']['guide_sha256']='wrong'
   else:source['review_declaration']['protocol']='not_selected'
   with self.assertRaises(ValueError):lifecycle.seal(source,lifecycle.plan_splits(source),self.guide,self.root/field)
 def test_development_cannot_load_reserved_and_denied_access_is_logged(self):
  output,manifest=self.seal()
  protected=output/'protected'/'reserved.jsonl';protected.write_text('not valid JSON')
  self.assertEqual(len(lifecycle.load_release(output)[2]),8)
  self.assertEqual(len(harness.guarded_load(output)[2]),8)
  with self.assertRaises(ValueError):lifecycle.load_release(output,'reserved',reason='Unit test denied access')
  log=json.loads((output/'reserved-access.jsonl').read_text());self.assertFalse(log['allowed']);self.assertIn('utc',log)
  with self.assertRaises(ValueError):harness.guarded_load(output,'reserved',self.registry(manifest),'test','Unit test integrity mismatch')
 def test_authorized_reserved_path_checks_frozen_manifest_and_item_hashes(self):
  output,manifest=self.seal();registry=self.registry(manifest)
  loaded=harness.guarded_load(output,'reserved',registry,'test','Unit test authorized access')
  self.assertEqual(len(loaded[2]),8)
  self.assertTrue(all(r['split']=='reserved' for r in loaded[2]))
  path=output/'manifest.json';modified=json.loads(path.read_text());modified['dataset_version']='tampered';path.write_text(json.dumps(modified))
  with self.assertRaises(ValueError):harness.guarded_load(output,'reserved',registry,'test','Unit test manifest mutation')
 def test_legacy_development_bundle_cannot_be_relabelled_as_fresh_source(self):
  with self.assertRaises(ValueError):lifecycle.plan_splits({'format':'development-bundle-v1','items':self.source['items']})
 def test_exact_duplicates_or_incomplete_language_families_are_rejected(self):
  source=copy.deepcopy(self.source);source['items'][4]['text']=source['items'][0]['text']
  with self.assertRaises(ValueError):lifecycle.plan_splits(source)
  source=copy.deepcopy(self.source);source['items'].pop()
  with self.assertRaises(ValueError):lifecycle.plan_splits(source)
