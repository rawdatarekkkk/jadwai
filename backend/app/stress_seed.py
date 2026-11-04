"""Add labelled synthetic scale data transactionally; preserve all existing records.

Run explicitly as `python -m app.stress_seed` after loading the local .env.
Repeated runs do not duplicate or overwrite the synthetic batch.
"""
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5
from sqlalchemy import select
from app.academic import validate_record
from app.dependencies import event, workspace_lock
from app.models import Record, Rule, SessionLocal, User
from app.schemas import RuleInput
from app.schedules import snapshot_of


def ident(code):
    return str(uuid5(NAMESPACE_URL, 'jadwai:stress-demo:v1:' + code))


def planned_records(period_minutes):
    records = []
    def add(kind, code, **body):
        row = {'id': ident(code), 'kind': kind, 'code': code, **body}
        records.append(row)
        return row['id']
    teachers = [add('instructors', f'LOAD-T{i+1:02}', name=f'[Demo] Dr. {name}', department='Synthetic stress-test department') for i,name in enumerate([
        'Layla Mansour','Youssef Adel','مريم حسن','Kareem Fathy','Nadine Samir','عمر خالد',
        'Dina Ibrahim','Tarek Mahmoud','Salma Nabil','Ali Mostafa','Farah Ahmed','Hassan Amin',
        'Rania Sherif','Bilal Saad','Nour El Din','Hana Gamal','Malak Zaki','Adam Fouad',
        'Jana Salah','Ziad Wael','Reem Hossam','Amir Medhat','Aya Sameh','Seif Ashraf'])]
    groups = [add('groups', f'LOAD-G{i+1:02}', name=f'[Demo] Year {i//6+1} · Group {i%6+1}', size=20+(i%6)*3, year=i//6+1, major=['Computer Science','Software Engineering','Information Systems'][(i%6)//2]) for i in range(18)]
    for zone in range(6):
        for room in range(3):
            lab = room == 2
            add('rooms',f'LOAD-R{zone+1}{room+1}',name=f'[Demo] {"Computing Lab" if lab else "Teaching Room"} {zone+1}.{room+1}',capacity=36 if lab else 40+room*20,room_type='lab' if lab else 'lecture',equipment=[f'demo-zone-{zone+1}','computers' if lab else 'projector'])
    subjects=['Algorithms','Artificial Intelligence','قواعد البيانات','Software Architecture','Computer Networks','Cybersecurity','Data Science','Operating Systems','هندسة البرمجيات','Human–Computer Interaction','Distributed Systems','Digital Logic','Machine Learning','Cloud Computing','Mathematics','Web Engineering','Robotics','Information Systems','Programming Languages','Research Methods']
    for i in range(60):
        zone=i%6
        component=['lecture','tutorial','lab'][i%3]
        add('courses', f'LOAD-A{i+1:03}', name=f'[Demo] {subjects[i%20]} · {component.title()} {i//20+1}', activity_type=component, sessions=1+i%2,
            duration=120 if component=='lab' else 60, eligible_instructors=[teachers[zone*4+(i//6)%4], teachers[zone*4+((i//6)+1)%4]],
            group_ids=[groups[i%18]], required_equipment=[f'demo-zone-{zone+1}','computers' if component=='lab' else 'projector'])
    return records,teachers


def seed():
    with SessionLocal.begin() as db:
        ws=workspace_lock(db)
        user=db.scalar(select(User).where(User.email==os.environ.get('JADWAI_ADMIN_EMAIL','admin@jadwai.local').lower(),User.active.is_(True),User.role=='administrator'))
        if not user:
            raise RuntimeError('The configured active administrator must exist before loading demo data.')
        records,teachers=planned_records(ws.period_minutes)
        expected={r['id'] for r in records}
        present=set(db.scalars(select(Record.id).where(Record.id.in_(expected))))
        if present:
            if present!=expected:
                raise RuntimeError('A partial demo batch exists. No records changed; review it before retrying.')
            print(json.dumps({'status':'already_loaded','records':len(expected),'version':ws.version}))
            return
        codes=set(db.scalars(select(Record.code)))
        if codes & {r['code'] for r in records}:
            raise RuntimeError('Demo codes collide with existing data. No records changed.')
        if ws.end_hour-ws.start_hour<4 or not ws.days:
            raise RuntimeError('The demo requires at least a four-hour teaching window and one teaching day.')
        backup=snapshot_of(db,ws)
        # Include draft rules too; generation snapshots deliberately exclude them.
        backup['rules']=[{'id':r.id,'status':r.status,'approved_by':r.approved_by,**r.data} for r in db.scalars(select(Rule))]
        directory=Path(__file__).resolve().parents[2]/'backups'
        directory.mkdir(mode=0o700,exist_ok=True)
        filename=directory/('before-stress-data-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        filename.write_text(json.dumps(backup,ensure_ascii=False,indent=2));filename.chmod(0o600)
        for row in records:
            body={k:v for k,v in row.items() if k not in ('id','kind')}
            body=validate_record(row['kind'],body,db)
            db.add(Record(id=row['id'],kind=row['kind'],data=body))
            db.flush()
        # Exercise mandatory and preferred windows without contradicting the
        # existing calendar or touching existing instructors/rules.
        for i,teacher in enumerate(teachers):
            preferred=i%2==1
            code=f'LOAD-RULE-{i+1:02}'
            body=RuleInput(title=f'[Demo] {"Preferred teaching window" if preferred else "Unavailable window"} {i+1}',instructor_id=teacher,
                type='preferred_period' if preferred else 'unavailable',day=ws.days[i%len(ws.days)],
                start_hour=ws.start_hour+(2 if preferred else 0),end_hour=min(ws.end_hour,ws.start_hour+(6 if preferred else 2)),strength='preferred' if preferred else 'mandatory').model_dump()
            db.add(Rule(id=ident(code),data=body,status='approved',approved_by=user.id))
        event(db,ws,user,'demo.loaded','Large synthetic dataset: 120 academic records, 24 approved demo rules',changes_inputs=True)
        db.flush()
        print(json.dumps({'status':'added','records':dict(Counter(r['kind'] for r in records)),'new_weekly_sessions':sum(r.get('sessions',0) for r in records),'approved_demo_rules':24,'version':ws.version,'backup':str(filename)},ensure_ascii=False))

if __name__=='__main__':
    seed()
