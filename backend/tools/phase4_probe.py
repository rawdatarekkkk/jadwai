"""Offline synthetic scale probe; never writes academic data to PostgreSQL."""
import argparse,csv,json,platform,sys
from pathlib import Path
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.solver import generate
from app.validation import validate_schedule
from app.provenance import seal_snapshot,SolverSettings

def instance(count):
 records=[]
 for i in range(8):
  records.extend([{'id':f't{i}','kind':'instructors','name':f'Synthetic teacher {i}'},{'id':f'g{i}','kind':'groups','size':20},{'id':f'r{i}','kind':'rooms','capacity':30,'room_type':'lecture','room_types':['lecture'],'equipment':[]}])
 for i in range(count):records.append({'id':f'a{i}','kind':'courses','name':f'Synthetic activity {i}','sessions':1,'duration':60,'activity_type':'lecture','eligible_instructors':[f't{i%8}'],'group_ids':[f'g{i%8}'],'required_equipment':[]})
 return {'calendar':{'days':['Saturday','Sunday','Monday','Tuesday','Wednesday','Thursday'],'start_hour':8,'end_hour':18,'period_minutes':30,'timezone':'Africa/Cairo'},'records':records,'rules':[]}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 rows=[]
 for count in [10,40,80,160]:
  snapshot=seal_snapshot(instance(count),SolverSettings(time_limit_seconds=2,search_workers=1,random_seed=42).model_dump())
  started=perf_counter();result=generate(snapshot);elapsed=perf_counter()-started
  report=validate_schedule(snapshot,result['assignments']) if result['status']=='completed' else None
  rows.append({'activities':count,'required_sessions':count,'scheduled_sessions':len(result['assignments']),'status':result['status'],'reason':result.get('reason'),'raw_status':result.get('solver_diagnostics',{}).get('raw_status'),'independent_validation_passed':report['passed'] if report else None,'elapsed_seconds':round(elapsed,6),'seed':42,'search_workers':1,'time_limit_seconds':2,'ortools_version':__import__('ortools').__version__,'python_version':platform.python_version(),'snapshot_sha256':snapshot['provenance']['snapshot_sha256'],'config_sha256':snapshot['provenance']['config_sha256']})
  if report and not report['passed']:raise RuntimeError('Independent validation failed')
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with args.output.open('x',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
