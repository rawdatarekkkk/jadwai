from copy import deepcopy
from app.provenance import seal_snapshot, verify_snapshot, fingerprint
from app.solver import generate
from app.schedule_worker import process_one
from test_schedules import example, setup_data, start
from test_workflows import login


def test_fingerprint_is_canonical_and_detects_changes():
    assert fingerprint({'a':1,'b':'ع'}) == fingerprint({'b':'ع','a':1})
    snap=seal_snapshot(example())
    assert verify_snapshot(snap)
    assert seal_snapshot(snap)==snap
    changed=deepcopy(snap); changed['records'][0]['name']='Changed'
    assert not verify_snapshot(changed)
    changed=deepcopy(snap); changed['provenance']['solver_config']['random_seed']=99
    assert not verify_snapshot(changed)
    assert verify_snapshot(example())


def test_solver_records_actual_parameters_and_raw_outcome():
    result=generate(example(),time_limit=1)
    d=result['solver_diagnostics']
    assert d['raw_status'] in ('OPTIMAL','FEASIBLE')
    assert d['ortools_version'] and d['solver_seconds']>=0
    assert 'max_time_in_seconds: 1' in d['parameters_text']
    assert 'random_seed: 42' in d['parameters_text']
    result=generate(example(),time_limit=0)
    assert result['solver_diagnostics']['raw_status']=='UNKNOWN'


def test_saved_run_retains_fingerprints_and_validation_version(environment):
    client,factory=environment
    login(client);setup_data(client,factory)
    ident=start(client).json()['id']
    assert process_one(factory)
    run=client.get('/api/schedules/'+ident).json()
    assert verify_snapshot(run['snapshot'])
    p=run['result']['provenance']
    assert p['snapshot']==run['snapshot']['provenance']
    assert p['validator_version'] and p['worker_elapsed_seconds']>=0
    assert run['result']['solver_diagnostics']['raw_status'] in ('OPTIMAL','FEASIBLE')


def test_worker_refuses_mismatched_snapshot(environment, monkeypatch):
    from app import schedule_worker
    client,factory=environment
    login(client);setup_data(client,factory)
    ident=start(client).json()['id']
    monkeypatch.setattr(schedule_worker, 'verify_snapshot', lambda snap: False)
    monkeypatch.setattr(schedule_worker, 'generate', lambda *args: (_ for _ in ()).throw(AssertionError('must not solve')))
    assert process_one(factory)
    run=client.get('/api/schedules/'+ident).json()
    assert run['status']=='failed'
    assert run['result']['reason']=='snapshot_integrity_failed'
    assert run['result']['assignments']==[]
