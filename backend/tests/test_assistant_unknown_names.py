from copy import deepcopy
from app.assistant import understand, answer
from test_assistant import VIEW


def turn(text, view, previous=None):
    meaning = understand(text, view, previous)
    reply = answer(meaning, view, False)
    meaning['asking'] = reply.get('asking', False)
    return meaning, reply


def test_unknown_programme_requires_clarification_and_preserves_context():
    view = deepcopy(VIEW)
    view['records'].append({'id': 'acs', 'kind': 'groups', 'data': {'major': 'Applied Computer Science & Informatics', 'year': 2, 'code': 'ACSI2-G1'}})
    state, _ = turn('new study group', view)
    state, reply = turn('cs', view, state)
    assert state['slots']['field'] == 'major'
    assert 'major' not in state['slots']['form']
    assert 'Which programme do you mean' in reply['text'][0]
    assert any(c['text'] == 'Applied Computer Science & Informatics' for c in reply['choices'])
    state, reply = turn('Applied Computer Science & Informatics', view, state)
    assert state['slots']['form']['major'] == 'Applied Computer Science & Informatics'
    assert state['slots']['field'] == 'year'
    assert 'Which year' in reply['text'][0]


def test_new_name_requires_explicit_selection_and_survives_next_turn():
    state, _ = turn('new study group', VIEW)
    state, _ = turn('Robotics', VIEW, state)
    state, reply = turn('use as new name', VIEW, state)
    assert state['slots']['form']['major'] == 'Robotics'
    assert state['slots']['field'] == 'year'
    state, reply = turn('2', VIEW, state)
    assert state['slots']['form']['major'] == 'Robotics'
    assert state['slots']['field'] == 'number'


def test_unknown_department_and_repeated_unknown_reply_stay_on_question():
    state, _ = turn('add Dr. Sara Ali', VIEW)
    state, reply = turn('cs', VIEW, state)
    assert state['slots']['field'] == 'department'
    assert 'department' not in state['slots']['form']
    state, reply = turn('nonsense', VIEW, state)
    assert state['slots']['field'] == 'department'
    assert 'nonsense' in reply['text'][0]
    state, reply = turn('Informatics', VIEW, state)
    assert state['slots']['form']['department'] == 'Informatics'
    assert state['slots']['field'] == 'day_off'


def test_legacy_unknown_name_is_rechecked_before_proposal():
    state = {'intent': 'create_record', 'slots': {'kind': 'groups', 'form': {'major': 'cs', 'year': 2, 'number': 1, 'size': 30}}, 'ambiguous': []}
    reply = answer(state, VIEW, False)
    assert reply['asking'] and reply['field'] == 'major'
    assert not reply.get('action')


def test_invalid_numeric_answer_does_not_advance():
    state, _ = turn('new study group', VIEW)
    state, _ = turn('Business Administration', VIEW, state)
    state, reply = turn('unknown', VIEW, state)
    assert state['slots']['field'] == 'year'
    assert 'year' not in state['slots']['form']


def test_ambiguous_programme_does_not_choose_first_match():
    view = deepcopy(VIEW)
    for i, name in enumerate(('Applied Computer Science & Informatics', 'Business Informatics')):
        view['records'].append({'id': str(i), 'kind': 'groups', 'data': {'major': name}})
    state, _ = turn('new study group', view)
    state, reply = turn('Informatics', view, state)
    assert state['slots']['field'] == 'major'
    assert 'major' not in state['slots']['form']
    assert len([c for c in reply['choices'] if 'Informatics' in c['label']]) == 3


def test_clarification_keeps_language():
    state, _ = turn('new study group', VIEW)
    state['slots']['ar'] = True
    state, reply = turn('cs', VIEW, state)
    assert 'تقصد' in reply['text'][0]
    assert not reply.get('action')
