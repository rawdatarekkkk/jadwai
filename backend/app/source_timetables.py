"""Administrator-only source timetable review; incomplete rows never feed the solver."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.dependencies import administrator, db_session
from app.models import SourceTimetable
router=APIRouter()

@router.get('/api/source-timetables')
def list_sources(user=Depends(administrator),db=Depends(db_session)):
    return [{'id':r.id,'source_document':r.source_document,'created_at':r.created_at,**r.payload} for r in db.scalars(select(SourceTimetable).order_by(SourceTimetable.created_at.desc()))]
