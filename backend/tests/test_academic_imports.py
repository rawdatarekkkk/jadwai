import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_workflows import login,version


def create_group(client):
    response=client.post('/api/records/groups',headers=version(client),json={'name':'Group','code':'G','size':20})
    assert response.status_code==201
    return response.json()['id']


def test_import_preview_has_no_side_effects_and_commit_is_atomic(environment):
    client,_=environment
    login(client)
    content='name,code,capacity,room_type\nRoom A,A,30,lecture\nBad room,B,not-a-number,lab\n'
    preview=client.post('/api/imports/rooms/preview',json={'csv':content})
    assert preview.status_code==200
    assert [r['valid'] for r in preview.json()['rows']]==[True,False]
    assert client.get('/api/workspace').json()['version']==1
    assert client.post('/api/imports/rooms/commit',headers=version(client),json={'csv':content}).status_code==422
    assert not any(r['kind']=='rooms' for r in client.get('/api/workspace').json()['records'])
    valid=content.replace('not-a-number','40')
    assert client.post('/api/imports/rooms/commit',headers=version(client),json={'csv':valid}).status_code==201
    ws=client.get('/api/workspace').json()
    assert ws['version']==2
    assert len([r for r in ws['records'] if r['kind']=='rooms'])==2


def test_import_stale_preview_and_duplicate_rows(environment):
    client,_=environment
    login(client)
    content='name,code,size\nGroup A,A,20\nGroup B,A,30\n'
    assert client.post('/api/imports/groups/preview',json={'csv':content}).json()['valid'] is False
    content=content.replace('Group B,A','Group B,B')
    preview=client.post('/api/imports/groups/preview',json={'csv':content}).json()
    create_group(client)
    assert client.post('/api/imports/groups/commit',headers={'If-Match':f'"{preview["version"]}"'},json={'csv':content}).status_code==409


def test_activity_import_resolves_existing_codes_and_missing_refs_are_errors(environment):
    client,_=environment
    login(client)
    create_group(client)
    content='name,code,activity_type,sessions,duration,eligible_instructor_codes,group_codes\nCourse,C,lecture,2,60,TEST,G\n'
    assert client.post('/api/imports/courses/preview',json={'csv':content.replace('TEST','MISSING')}).json()['valid'] is False
    assert client.post('/api/imports/courses/commit',headers=version(client),json={'csv':content}).status_code==201
    activity=next(r for r in client.get('/api/workspace').json()['records'] if r['kind']=='courses')
    assert activity['eligible_instructors']==['teacher']


def test_database_rejects_missing_typed_details_and_foreign_key_corruption(environment):
    client,factory=environment
    login(client)
    group=create_group(client)
    response=client.post('/api/records/courses',headers=version(client),json={'name':'Course','code':'C','activity_type':'lecture','sessions':2,'duration':60,'eligible_instructors':['teacher'],'group_ids':[group]})
    assert response.status_code==201
    with factory() as db:
        with pytest.raises(DBAPIError):
            db.execute(text("INSERT INTO record(id,kind,name,code) VALUES('orphan','rooms','Orphan','ORPHAN')"))
            db.commit()
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(text('UPDATE activity_instructor SET instructor_id=:wrong'),{'wrong':group})
            db.commit()
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(text('DELETE FROM activity_group'))
            db.commit()


def test_relational_migration_roundtrip_preserves_inputs_and_equipment(environment):
    client,factory=environment
    login(client)
    group=create_group(client)
    assert client.post('/api/records/rooms',headers=version(client),json={'name':'Lab','code':'L','capacity':30,'room_type':'lab','equipment':['computers']}).status_code==201
    assert client.post('/api/records/courses',headers=version(client),json={'name':'Course','code':'C','activity_type':'lab','sessions':1,'duration':60,'eligible_instructors':['teacher'],'group_ids':[group],'required_equipment':['computers']}).status_code==201
    before=client.get('/api/workspace').json()
    config=Config('alembic.ini')
    with factory.kw['bind'].begin() as connection:
        config.attributes['connection']=connection
        command.downgrade(config,'0005')
        command.upgrade(config,'head')
    after=client.get('/api/workspace').json()
    # Upgrading now adds parent-course links to legacy activities while preserving
    # every academic input that existed before the catalogue migration.
    after_records = [dict(r) for r in after['records']]
    for record in after_records:
        if record['kind'] == 'courses':
            parent = next(c for c in after['course_catalog'] if c['id'] == record['course_id'])
            assert parent['name'] == record['name']
            assert set(record['eligible_instructors']) <= set(parent['eligibility'][record['activity_type']])
            assert set(record['group_ids']) <= set(parent['group_ids'])
            record['course_id'] = next(r for r in before['records'] if r['id'] == record['id']).get('course_id')
    assert before['records']==after_records
    assert before['version']==after['version']
