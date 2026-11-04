import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import harness
import runner

class HarnessTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.registry=harness.Registry(self.root/'versions')
  self.manifest={'schema_version':'test-v1'}
 def tearDown(self):self.temp.cleanup()
 def config(self):
  for kind in ('prompt','fewshot'):self.registry.register(kind,'v1','synthetic unit-test material','Unit fixture','confirmatory')
  return {'provider':'test-double','model':'unit-test-only','schema_version':'test-v1','prompt_version':'v1','fewshot_version':'v1','decoding':{'temperature':0},'timeout_seconds':10,'retry_limit':0,'repetitions':1}
 def test_version_immutability_and_hashes(self):
  self.registry.register('prompt','v1','original','Initial draft')
  with self.assertRaises(FileExistsError):self.registry.register('prompt','v1','replacement','Overwrite attempt')
  path=self.registry.path('prompt','v1');record=json.loads(path.read_text());record['content']='tampered';path.write_text(json.dumps(record))
  with self.assertRaises(ValueError):self.registry.read('prompt','v1')
 def test_configuration_template_requires_actual_experiment_choices(self):
  template=json.loads((Path(__file__).resolve().parents[1]/'run-config.template.json').read_text())
  with self.assertRaises(ValueError):harness.validate_configuration(template,{'schema_version':'proposal-contract-v1'})
  template.update(provider='test-double',model='unit-test-only',prompt_version='v1',fewshot_version='v1',decoding={'temperature':0},retry_limit=0,repetitions=1,timeout_seconds=10)
  harness.validate_configuration(template,{'schema_version':'proposal-contract-v1'})
 def test_freeze_requires_complete_config_and_confirmatory_material(self):
  config=self.config();self.registry.freeze('v1',config,'Unit fixture freeze',self.manifest)
  self.assertEqual(self.registry.frozen('v1',self.manifest)['content']['configuration'],config)
  for key in ['retry_limit','timeout_seconds','repetitions','decoding','model']:
   bad=copy.deepcopy(config);bad.pop(key)
   with self.assertRaises(ValueError):self.registry.freeze('bad',bad,'Incomplete config',self.manifest)
  with self.assertRaises(ValueError):self.registry.frozen('v1',{'schema_version':'changed'})
 def test_development_prompt_cannot_be_frozen_for_reserved_scoring(self):
  config=self.config();self.registry.register('prompt','dev','development template','Dev only')
  config['prompt_version']='dev'
  with self.assertRaises(ValueError):self.registry.freeze('bad',config,'Should refuse',self.manifest)
 def test_reserved_denial_is_logged_without_loading_labels(self):
  (self.root/'manifest.json').write_text(json.dumps(self.manifest))
  with self.assertRaises(ValueError):harness.guarded_load(self.root,'reserved',reason='Unit test denial')
  record=json.loads((self.root/'guard-access-log.jsonl').read_text())
  self.assertFalse(record['allowed'])
  self.assertFalse((self.root/'data').exists())
 def test_family_cluster_intervals_preserve_perfect_and_missing_outputs(self):
  _,contexts,rows=runner.load();rows=rows[:8]
  predictions=[{'id':r['id'],'output':copy.deepcopy(r['gold'])} for r in rows]
  result=harness.clustered_score(rows,contexts,predictions,replicates=100,seed=7)
  interval=result['uncertainty']['intervals']['end_to_end_accuracy']
  self.assertEqual(interval['estimate'],1)
  self.assertEqual(interval['lower'],1)
  self.assertEqual(interval['upper'],1)
  missing=harness.clustered_score(rows,contexts,[],replicates=100,seed=7)
  self.assertEqual(missing['uncertainty']['intervals']['end_to_end_accuracy']['estimate'],0)
  self.assertEqual(result,harness.clustered_score(rows,contexts,predictions,replicates=100,seed=7))
 def test_known_agreement_and_undefined_kappa(self):
  result=harness.agreement({'a':'yes','b':'yes','c':'no','d':'no'},{'a':'yes','b':'no','c':'no','d':'no'})
  self.assertEqual(result['raw_agreement'],.75);self.assertEqual(result['cohen_kappa'],.5)
  self.assertIsNone(harness.agreement({'a':'yes'},{'a':'yes'})['cohen_kappa'])
  with self.assertRaises(ValueError):harness.agreement({'a':'yes'},{'b':'yes'})
 def test_single_family_has_no_uncertainty_interval(self):
  _,contexts,rows=runner.load();family=rows[0]['family_id'];rows=[r for r in rows if r['family_id']==family]
  result=harness.clustered_score(rows,contexts,[],replicates=100)
  self.assertIsNone(result['uncertainty']['intervals']['end_to_end_accuracy']['lower'])
 def test_authorized_reserved_load_checks_frozen_dependencies_before_labels(self):
  from unittest.mock import patch
  config=self.config();self.registry.freeze('v1',config,'Unit fixture freeze',self.manifest)
  (self.root/'manifest.json').write_text(json.dumps(self.manifest))
  with patch.object(runner,'load',return_value=('manifest','contexts','rows')) as loader:
   result=harness.guarded_load(self.root,'reserved',self.registry,'v1','Unit test authorized guarded loading')
   self.assertEqual(result,('manifest','contexts','rows'))
   loader.assert_called_once_with(self.root,'reserved',True,'Unit test authorized guarded loading','guarded-score')
  self.assertTrue(json.loads((self.root/'guard-access-log.jsonl').read_text())['allowed'])
  path=self.registry.path('prompt','v1');record=json.loads(path.read_text());record['content']='modified';path.write_text(json.dumps(record))
  with patch.object(runner,'load') as loader:
   with self.assertRaises(ValueError):harness.guarded_load(self.root,'reserved',self.registry,'v1','Unit test tampered dependencies')
   loader.assert_not_called()
 def test_percentile_interpolation_on_hand_computed_values(self):
  self.assertEqual(harness.percentile([0,1,2,3,4],.25),1)
  self.assertEqual(harness.percentile([0,10],.025),.25)
  self.assertIsNone(harness.percentile([],.5))
 def test_versions_cannot_escape_registry(self):
  with self.assertRaises(ValueError):self.registry.register('prompt','../outside','x','bad path')
