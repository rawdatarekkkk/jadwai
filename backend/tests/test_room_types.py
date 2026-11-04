import pytest
from pydantic import ValidationError
from app.schemas import Room
from app.validation import validate_schedule
from test_schedules import example


def test_multiple_room_uses_and_legacy():
    assert Room(name='Hall', code='H', capacity=50, room_types=['lecture', 'exam_hall']).room_types == ['lecture', 'exam_hall']
    assert Room(name='Lab', code='L', capacity=50, room_type='lab').room_types == ['lab']
    for types in ([], ['office'], ['lab', 'lab']):
        with pytest.raises(ValidationError):
            Room(name='Bad', code='B', capacity=10, room_types=types)


def test_validator_uses_all_selected_types():
    snapshot = example()
    room = next(r for r in snapshot['records'] if r['kind'] == 'rooms')
    room['room_type'] = 'exam_hall'
    room['room_types'] = ['exam_hall', 'lecture']
    from app.solver import generate
    result = generate(snapshot)
    # Solver and independent validator must agree about secondary room uses.
    assert result['status'] == 'completed'
    assert validate_schedule(snapshot, result['assignments'])['passed']
    room['room_types'] = ['exam_hall']
    assert not validate_schedule(snapshot, result['assignments'])['passed']
    assert generate(snapshot)['reason'] == 'no_suitable_room'


def test_room_types_persist(environment):
    from test_workflows import login, version
    client, _ = environment
    login(client)
    response = client.post('/api/records/rooms', headers=version(client), json={
        'name': 'Shared hall', 'code': 'SH', 'capacity': 80,
        'room_types': ['lecture', 'lab', 'exam_hall'],
    })
    assert response.status_code == 201
    rooms = client.get('/api/workspace').json()['records']
    assert next(r for r in rooms if r['code'] == 'SH')['room_types'] == ['lecture', 'lab', 'exam_hall']
