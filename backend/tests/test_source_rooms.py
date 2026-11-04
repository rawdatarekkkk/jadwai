from app.schemas import Room
from app.solver import generate
from app.validation import validate_schedule
from app.preflight import inspect_inputs
from test_schedules import example
from test_workflows import login,version


def test_unknown_source_rooms_are_preserved_but_not_used(environment):
    client,_=environment;login(client)
    body={'name':'S3.234','code':'S3.234','capacity':None,'room_types':[],'source_info':{'source_document':'Winter schedule.xlsx','references':[{'sheet':'Saturday','cell':'E4'}]}}
    response=client.post('/api/records/rooms',headers=version(client),json=body)
    assert response.status_code==201
    room=next(r for r in client.get('/api/workspace').json()['records'] if r['code']=='S3.234')
    assert room['capacity'] is None and room['room_types']==[]
    ready={k:v for k,v in room.items() if k not in ('id','kind','source_info')}
    ready.update(capacity=50,room_types=['lecture'])
    assert client.put('/api/records/rooms/'+room['id'],headers=version(client),json=ready).status_code==200
    room=next(r for r in client.get('/api/workspace').json()['records'] if r['code']=='S3.234')
    assert room['source_info']['source_document']=='Winter schedule.xlsx'


def test_pending_room_is_excluded_and_validation_rejects_assignments_to_it():
    snapshot=example();rows=generate(snapshot)['assignments']
    room=next(r for r in snapshot['records'] if r['kind']=='rooms')
    room.update(capacity=None,room_type=None,room_types=[])
    assert generate(snapshot)['reason']=='no_suitable_room'
    assert 'room_suitability' in validate_schedule(snapshot,rows)['errors']
    checks=inspect_inputs(snapshot)
    assert any(w['code']=='room_setup_missing' for w in checks['warnings'])
