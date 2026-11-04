"""Apply the owner's approved five-period/90-minute timetable conversion."""
import json
import os
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import select
from app.dependencies import event,workspace_lock
from app.models import ActivityDetail,SessionLocal,User
from app.schedules import snapshot_of

PERIODS=[{'start':s,'end':e} for s,e in [(510,600),(615,705),(720,810),(825,915),(945,1035)]]


def apply():
    with SessionLocal.begin() as db:
        ws=workspace_lock(db)
        activities=db.scalars(select(ActivityDetail)).all()
        if ws.teaching_periods==PERIODS and all(a.duration==90 for a in activities):
            print(json.dumps({'status':'already_applied','version':ws.version}))
            return
        actor=db.scalar(select(User).where(User.email==os.environ.get('JADWAI_ADMIN_EMAIL','admin@jadwai.local').lower(),User.active.is_(True),User.role=='administrator'))
        if not actor:raise RuntimeError('Configured administrator missing')
        saved=snapshot_of(db,ws)
        directory=Path(__file__).resolve().parents[2]/'backups'
        directory.mkdir(mode=0o700,exist_ok=True)
        backup=directory/('before-reference-periods-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        backup.write_text(json.dumps(saved,ensure_ascii=False,indent=2));backup.chmod(0o600)
        ws.teaching_periods=PERIODS
        ws.start_hour,ws.end_hour,ws.period_minutes=8,22,30
        for activity in activities:activity.duration=90
        event(db,ws,actor,'calendar.reference_periods_applied',f'{len(activities)} activities converted to 90 minutes; five reference periods',changes_inputs=True)
        db.flush()
        print(json.dumps({'status':'applied','activities':len(activities),'version':ws.version,'backup':str(backup),'periods':PERIODS}))

if __name__=='__main__':apply()
