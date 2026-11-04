import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('jadwai_evaluation',ROOT/'runner.py')
eval=importlib.util.module_from_spec(spec);spec.loader.exec_module(eval)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'data',self.root/'data')
        shutil.copy(ROOT/'manifest.json',self.root/'manifest.json')
        manifest=eval.read_json(ROOT/'manifest.json')
        for name in manifest['files']:
            if not name.startswith('data/'):shutil.copy(ROOT/name,self.root/name)
        _,self.contexts,self.rows=eval.load(self.root)
    def tearDown(self):self.temp.cleanup()
    def oracle(self):
        # Unit-test fixture only. Copying labels is never a model experiment.
        return [{'id':r['id'],'output':copy.deepcopy(r['gold'])} for r in self.rows]
    def test_all_splits_validate_and_keep_families_together(self):
        result=eval.validate(self.root,True,'Unit test of synthetic corpus structure')
        self.assertEqual(result['counts']['development']['cases'],96)
        self.assertEqual(result['counts']['reserved']['cases'],32)
        self.assertFalse(result['blind_test'])
    def test_reserved_requires_opt_in_and_logs_reason(self):
        with self.assertRaises(ValueError):eval.load(self.root,'reserved')
        with self.assertRaises(ValueError):eval.load(self.root,'reserved',True,'')
        eval.load(self.root,'reserved',True,'Unit test reserved access control')
        self.assertTrue((self.root/'access-log.jsonl').exists())
    def test_default_does_not_read_reserved(self):
        (self.root/'data/reserved/cases.jsonl').write_text('not json')
        self.assertEqual(len(eval.load(self.root)[2]),96)
    def test_mutated_corpus_fails_manifest_check(self):
        with (self.root/'data/development/cases.jsonl').open('a') as out:out.write('\n')
        with self.assertRaises(ValueError):eval.load(self.root)
    def test_oracle_self_test_is_exact(self):
        result=eval.score(self.rows,self.contexts,self.oracle(),'raw')
        self.assertEqual(result['end_to_end_accuracy'],1)
        self.assertEqual(result['family_consistency']['all_exact_families'],24)
        self.assertIsNone(result['telemetry']['cost_usd']['sum'])
    def test_missing_predictions_are_not_dropped(self):
        result=eval.score(self.rows,self.contexts,[],'raw')
        self.assertEqual(result['case_count'],96)
        self.assertEqual(result['missing_predictions'],96)
        self.assertEqual(result['end_to_end_accuracy'],0)
    def test_unknown_and_duplicate_ids_fail(self):
        for rows in ([{'id':'unknown'}],self.oracle()+[self.oracle()[0]]):
            with self.assertRaises(ValueError):eval.score(self.rows,self.contexts,rows,'raw')
    def test_hallucinated_target_is_invalid_and_false_positive(self):
        predictions=self.oracle()
        predictions[0]['output']['proposals'][0]['data']['instructor_id']='invented'
        result=eval.score(self.rows,self.contexts,predictions,'raw')
        self.assertEqual(result['cases_with_unknown_entity_reference'],1)
        self.assertLess(result['metrics']['proposals']['precision'],1)
        self.assertLess(result['end_to_end_accuracy'],1)
    def test_titles_and_proposal_order_are_not_semantic(self):
        predictions=self.oracle()
        for row in predictions:
            row['output']['proposals'].reverse()
            for p in row['output']['proposals']:
                if p['kind']=='rule':p['data']['title']='A different useful label'
        self.assertEqual(eval.score(self.rows,self.contexts,predictions,'raw')['end_to_end_accuracy'],1)
    def test_extra_duplicate_proposal_fails(self):
        predictions=self.oracle();predictions[0]['output']['proposals']*=2
        result=eval.score(self.rows,self.contexts,predictions,'raw')
        self.assertFalse(result['cases'][0]['exact'])
        self.assertLess(result['metrics']['proposals']['precision'],1)
    def test_boolean_hours_and_nonfinite_cost_are_rejected(self):
        context=next(iter(self.contexts.values()))
        proposal={'kind':'instructor_weekly_limit','data':{'instructor_id':'i-nour-hassan','max_weekly_hours':True}}
        self.assertIn('invalid_hours',eval.proposal_errors(proposal,context))
        predictions=self.oracle();predictions[0]['metadata']={'cost_usd':float('nan')}
        with self.assertRaises(ValueError):eval.score(self.rows,self.contexts,predictions,'raw')
    def test_malformed_nested_outputs_fail_without_crashing(self):
        predictions=self.oracle();predictions[0]['output']['decision']=[]
        predictions[1]['output']['proposals'][0]['data']['type']=[]
        result=eval.score(self.rows,self.contexts,predictions,'raw')
        self.assertEqual(result['valid_outputs'],94)
    def test_empty_unsupported_class_has_no_invented_success(self):
        row=next(r for r in self.rows if r['gold']['decision']=='ready')
        result=eval.score([row],self.contexts,[{'id':row['id'],'output':row['gold']}],'raw')
        self.assertIsNone(result['metrics']['unsupported']['recall'])
    def test_cli_export_is_gold_free_and_preserves_existing_files(self):
        out=self.root/'inputs.jsonl'
        command=[sys.executable,str(ROOT/'runner.py'),'export-inputs','--output',str(out)]
        completed=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        rows=eval.read_rows(out)
        self.assertEqual(len(rows),96)
        self.assertTrue(all(set(r)=={'id','language','context_id','text'} for r in rows))
        before=out.read_bytes()
        self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
        self.assertEqual(out.read_bytes(),before)
    def test_cli_scoring_empty_predictions_is_explicit_software_check(self):
        predictions=self.root/'no-predictions.jsonl';predictions.write_text('')
        config=self.root/'self-test-config.json'
        config.write_text(json.dumps({'provider':'software-self-test','model':'no-model','prompt_version':'unit-test-only','schema_version':'proposal-contract-v1'}))
        out=self.root/'score.json'
        completed=subprocess.run([sys.executable,str(ROOT/'runner.py'),'score','--predictions',str(predictions),'--config',str(config),'--output',str(out)],capture_output=True,text=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        report=eval.read_json(out)
        self.assertEqual(report['missing_predictions'],96)
        self.assertFalse(report['independently_adjudicated'])
        self.assertIsNone(report['telemetry']['cost_usd']['sum'])
        self.assertTrue(report['manifest_sha256'] and report['scorer_sha256'])
    def builder(self):
        spec=importlib.util.spec_from_file_location('synthetic_builder',ROOT/'build_corpus.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.ROOT=self.root
        return module
    def test_packaging_is_reproducible(self):
        before=(self.root/'manifest.json').read_bytes()
        self.builder().build()
        self.assertEqual((self.root/'manifest.json').read_bytes(),before)
    def test_reviewed_release_is_not_overwritten(self):
        manifest=eval.read_json(self.root/'manifest.json');manifest['independently_adjudicated']=True
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        before=(self.root/'data/development/cases.jsonl').read_bytes()
        with self.assertRaises(ValueError):self.builder().build()
        self.assertEqual((self.root/'data/development/cases.jsonl').read_bytes(),before)
    def test_rule_data_matches_backend_contract(self):
        import sys
        sys.path.insert(0,str(ROOT.parent/'backend'))
        try:
            from app.schemas import RuleInput,RealismPolicy
            _,_,reserved=eval.load(self.root,'reserved',True,'Unit test schema compatibility for reserved synthetic labels')
            for row in self.rows+reserved:
                for p in row['gold']['proposals']:
                    if p['kind']=='rule':RuleInput.model_validate(p['data'])
                    elif p['kind']=='realism_policy':RealismPolicy.model_validate(p['data'])
        except ModuleNotFoundError as exc:
            self.skipTest('Run under backend venv for backend schema compatibility: '+str(exc))

if __name__=='__main__':unittest.main()
