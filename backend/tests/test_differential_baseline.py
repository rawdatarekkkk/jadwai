"""Exact assignment fixing checks the independent validator against the CP model."""
import ast
from copy import deepcopy
from pathlib import Path
import random
import pytest
from app.solver import generate
from app.validation import validate_schedule
from test_schedules import example

@pytest.mark.parametrize('seed',range(8))
def test_random_small_instances_and_corruptions(seed):
 rng=random.Random(seed);snapshot=example()
 snapshot['records'][4]['duration']=rng.choice([30,60,90])
 snapshot['records'][5]['duration']=rng.choice([30,60,90])
 snapshot['records'][3]['capacity']=rng.choice([25,30,40])
 result=generate(snapshot)
 assert result['status']=='completed'
 rows=result['assignments']
 assert validate_schedule(snapshot,rows)['passed']
 assert generate(snapshot,fixed_assignments=rows)['status']=='completed'
 bad=deepcopy(rows)
 bad[1].update({k:bad[0][k] for k in ('day','start_minute')})
 bad[1]['end_minute']=bad[1]['start_minute']+snapshot['records'][4]['duration']
 assert not validate_schedule(snapshot,bad)['passed']
 assert generate(snapshot,fixed_assignments=bad)['status']=='infeasible'

def test_fixed_hook_refuses_partial_or_duplicate_occurrences():
 snapshot=example();rows=generate(snapshot)['assignments']
 for bad in [rows[:-1],rows+[rows[0]]]:
  with pytest.raises(ValueError):generate(snapshot,fixed_assignments=bad)

def test_validator_dependency_graph_cannot_reach_solver():
 root=Path(__file__).resolve().parents[1]/'app'
 pending=['validation'];seen=set()
 while pending:
  name=pending.pop()
  if name in seen:continue
  seen.add(name)
  assert name not in {'solver','schedule_worker','realism_model','preflight'}
  for node in ast.walk(ast.parse((root/(name+'.py')).read_text())):
   if isinstance(node,ast.ImportFrom) and node.module:
    assert not node.module.startswith('ortools')
    if node.module.startswith('app.'):
     dependency=node.module.split('.')[1]
     if (root/(dependency+'.py')).exists():pending.append(dependency)
