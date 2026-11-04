import json
from pathlib import Path
from app.import_source_timetable import import_extraction
from app.models import Record,SourceTimetable
from sqlalchemy import select,func

def test_source_import_is_idempotent_and_admin_only(environment,tmp_path):
 from test_workflows import login
 client,factory=environment
 payload={'source_document':'schedule.xlsx','source_sha256':'a'*64,'current_timetable_entries':1,'explicit_room_identifiers':1}
 entry={'source_sheet':'Saturday','source_cell':'E4','course_label_candidate':'Algorithms'}
 files={'summary.json':payload,'timetable.json':[entry],'rooms.json':{'rooms':[{'code':'A.100','references':[]}]},'day-off-blocks.json':[],'course-label-candidates.json':[],'cohort-labels.json':[],'instructor-mentions.json':[]}
 for name,data in files.items():(tmp_path/name).write_text(json.dumps(data))
 with factory.begin() as db:
  preview=import_extraction(db,tmp_path)
  assert preview['blocks_to_import']==1 and preview['rooms_to_create']==1
  assert db.scalar(select(func.count()).select_from(SourceTimetable))==0
 with factory.begin() as db:
  result=import_extraction(db,tmp_path,True,tmp_path/'backup.json')
  assert result['imported']
 with factory.begin() as db:
  result=import_extraction(db,tmp_path,True)
  assert result['source_already_imported'] and result['rooms_to_create']==0
  assert db.scalar(select(func.count()).select_from(SourceTimetable))==1
  assert db.scalar(select(func.count()).select_from(Record).where(Record.kind=='courses'))==0
 login(client)
 response=client.get('/api/source-timetables')
 assert response.status_code==200
 assert response.json()[0]['entries'][0]['source_cell']=='E4'
 client.post('/api/auth/logout');login(client,'viewer@example.test')
 assert client.get('/api/source-timetables').status_code==403
