"""One-shot, checksum-idempotent import of reviewed local extraction files."""
import argparse,json,re
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL
from collections import defaultdict
from sqlalchemy import select
from app.models import SessionLocal,SourceTimetable,Record,CourseCatalog,Workspace
from app.schemas import Room
from app.dependencies import event

def normalized(value):return re.sub(r'[^a-z0-9]','',value.casefold())

def import_extraction(db,directory,commit=False,backup=None):
    p=Path(directory)
    summary=json.loads((p/'summary.json').read_text())
    entries=json.loads((p/'timetable.json').read_text())
    assert len(entries)==summary['current_timetable_entries']
    assert len({(r['source_sheet'],r['source_cell']) for r in entries})==len(entries)
    checksum=summary['source_sha256']
    assert re.fullmatch('[a-f0-9]{64}',checksum)
    ws=db.scalar(select(Workspace).where(Workspace.id==1).with_for_update())
    records=db.scalars(select(Record)).all();catalog=db.scalars(select(CourseCatalog)).all()
    existing=db.scalar(select(SourceTimetable).where(SourceTimetable.source_sha256==checksum))
    codes={normalized(r.code) for r in records if r.kind=='rooms'}
    rooms=json.loads((p/'rooms.json').read_text())['rooms']
    missing=[r for r in rooms if normalized(r['code']) not in codes]
    names=defaultdict(set)
    for c in catalog:
        for name in [c.name,*((c.source_info or {}).get('name_variants') or [])]:names[normalized(name)].add(c.id)
    for row in entries:
        matches=names.get(normalized(row['course_label_candidate']),set())
        row['matched_course_id']=next(iter(matches)) if len(matches)==1 else None
    result={'source_document':summary['source_document'],'existing_catalogue_courses':len(catalog),'existing_room_records':sum(r.kind=='rooms' for r in records),'rooms_to_create':len(missing),'source_already_imported':bool(existing),'blocks_to_import':0 if existing else len(entries),'blocks_linked_to_existing_courses':sum(bool(r['matched_course_id']) for r in entries),'new_schedulable_activities':0}
    if not commit:return result
    if not existing or missing:
        if not backup:raise ValueError('A backup path is required for an import')
        destination=Path(backup)
        destination.parent.mkdir(parents=True,exist_ok=True)
        # Refuse to overwrite an earlier backup.
        with destination.open('x') as stream:
            json.dump({'workspace_version':ws.version,'records':[{'id':r.id,'kind':r.kind,'data':r.data} for r in records],'catalogue':[{'id':c.id,'name':c.name,'code':c.code,'source_info':c.source_info,'eligibility':c.eligibility,'group_ids':c.group_ids} for c in catalog],'source_timetables':[{'id':r.id,'source_sha256':r.source_sha256,'source_document':r.source_document,'payload':r.payload} for r in db.scalars(select(SourceTimetable))]},stream,default=str,ensure_ascii=False)
        destination.chmod(0o600)
        for room in missing:
            body=Room(name=room['code'],code=room['code'],capacity=None,room_types=[],source_info={'source_document':summary['source_document'],'references':room['references']}).model_dump()
            record=Record(id=str(uuid5(NAMESPACE_URL,'jadwai:source-room:'+normalized(room['code']))),kind='rooms');record.data=body;db.add(record)
        if not existing:
            payload={'summary':summary,'entries':entries}
            for file,key in [('day-off-blocks.json','day_off_blocks'),('course-label-candidates.json','course_labels'),('cohort-labels.json','cohort_labels'),('instructor-mentions.json','instructor_mentions')]:payload[key]=json.loads((p/file).read_text())
            db.add(SourceTimetable(id=str(uuid5(NAMESPACE_URL,'jadwai:source-timetable:'+checksum)),source_sha256=checksum,source_document=summary['source_document'],payload=payload))
        event(db,ws,None,'source_timetable.imported',f'{len(entries)} timetable blocks; {len(missing)} new rooms',changes_inputs=bool(missing))
        db.flush()
    result['imported']=True
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--commit',action='store_true');parser.add_argument('--backup');args=parser.parse_args()
    with SessionLocal.begin() as db:print(json.dumps(import_extraction(db,args.directory,args.commit,args.backup),indent=2))
