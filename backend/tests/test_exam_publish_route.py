"""The built-in route for "publish the exam timetable" (the fine-tuned model never learned to pick it)."""
import asyncio
from copy import deepcopy
import httpx
import pytest
from app.assistant import ARABIC, answer, understand
from app.assistant_capabilities import converse
from app.assistant_context import with_context
from app.main import app
from test_assistant import VIEW
from test_workflows import login

EXAM = {'id': 'exam-mid1', 'status': 'completed', 'kind': 'midterm', 'published': False, 'stale': False, 'halls': True,
        'name': 'Computing midterms', 'start_date': '2026-11-21', 'end_date': '2026-11-30'}
DRAFT = {'id': 'run-draft3', 'name': 'Draft 3', 'published': False, 'stale': False, 'on_screen': False, 'talked_about': False, 'complete': True, 'sessions': 212}


def exam_view(screen=True):
    """The held-out "exam-and-draft" scenario: an exam draft on the Exams page and an unpublished teaching draft."""
    v = deepcopy(VIEW)
    v.update(run=dict(DRAFT), newest=dict(DRAFT), exam_run=dict(EXAM), exam_drafts=[dict(EXAM)], published_exam=None)
    v['screen'] = {'page': 'exams', 'run_id': 'exam-mid1'} if screen else {}
    v['memory'] = {'exam_run': 'exam-mid1', 'schedule_focus': {'kind': 'exams', 'id': 'exam-mid1'}} if screen else {}
    return v


def reply_to(text, view):
    meaning = with_context(text, understand(text, view, None), view['memory'])
    return answer(meaning, view, bool(ARABIC.search(text)))


EN = 'Shall I publish Computing midterms, the exam timetable? Publishing re-validates it first.'
AR = 'أنشر جدول الامتحانات Computing midterms؟ النشر بيراجعه الأول.'


@pytest.mark.parametrize('text, expected', [
    # The held-out test family exam-publish-formal (finetuning/data/test.jsonl), 0/3 for the v3 and v4 models.
    ('please publish the exam schedule', EN), ('يرجى نشر جدول الامتحانات', AR), ('ممكن تنشر جدول الامتحانات؟', AR),
    # exam-publish-context / -arguments and other wordings.
    ('publish it', EN), ('publish this exam timetable', EN), ('publish the exam draft', EN), ('publish this midterm timetable', EN),
    ('can you publish the exams?', EN), ('انشر جدول الامتحانات ده', AR), ('انشر مسودة الامتحانات', AR), ('نشر جدول الامتحانات', AR),
    ('أنشر جدول الامتحانات', AR), ('عايز أنشر جدول الامتحانات', AR), ('ممكن تنشره؟', AR), ('من فضلك انشرها', AR),
    ('انشر جدول الامتحانات مش جدول المحاضرات', AR), ('publish the exams, not the teaching draft', EN),
])
def test_exam_publish_wordings_prepare_the_confirmable_exam_publish_action(text, expected):
    reply = reply_to(text, exam_view())
    assert reply['action'] == {'type': 'publish', 'what': 'exams', 'run_id': 'exam-mid1', 'label': 'نشر' if ARABIC.search(text) else 'Publish'}
    assert reply['text'] == [expected]


def test_replacing_the_published_exam_timetable_is_said():
    view = exam_view()
    view['published_exam'] = 'exam-old'
    assert reply_to('publish it', view)['text'][0].endswith('and it replaces the exam timetable published now.')


def test_published_is_not_a_request_to_publish():
    for text in ('is the exam timetable published?', 'هل جدول الامتحانات منشور؟', 'هو اتنشر؟'):
        assert understand(text, exam_view(), None)['intent'] != 'publish', text


def test_teaching_or_exam_unclear_asks_which_instead_of_guessing():
    view = exam_view(screen=False)
    for text in ('publish it', 'publish the exams and the teaching timetable'):
        reply = reply_to(text, view)
        assert not reply.get('action') and 'Which one should I publish' in reply['text'][0], text
        assert [c['text'] for c in reply['choices']] == ['publish the exam timetable', 'publish the teaching timetable']
    arabic = reply_to('انشره', view)
    assert not arabic.get('action') and arabic['choices'][0]['text'] == 'انشر جدول الامتحانات'
    # The answers to that question pick one.
    assert reply_to('publish the exam timetable', view)['action']['what'] == 'exams'
    assert reply_to('publish the teaching timetable', view)['action'] == {'type': 'publish', 'what': 'teaching', 'run_id': 'run-draft3', 'label': 'Publish'}


def test_several_exam_drafts_ask_which_one_and_the_name_picks_it():
    view = exam_view(screen=False)
    view['newest'] = None
    view['exam_drafts'].append({**EXAM, 'id': 'exam-fin', 'name': 'Computing finals', 'kind': 'final'})
    reply = reply_to('please publish the exam schedule', view)
    assert not reply.get('action') and reply['text'][0].startswith('There are 2 unpublished exam timetables: Computing midterms, Computing finals.')
    assert [c['text'] for c in reply['choices']] == ['publish Computing midterms', 'publish Computing finals']
    chosen = reply_to('publish Computing finals', view)
    assert chosen['action']['run_id'] == 'exam-fin' and chosen['text'][0].startswith('Shall I publish Computing finals')
    # The one on screen is not ambiguous.
    view['screen'] = {'page': 'exams', 'run_id': 'exam-mid1'}
    view['memory'] = {'exam_run': 'exam-mid1'}
    assert reply_to('please publish the exam schedule', view)['action']['run_id'] == 'exam-mid1'


def test_exam_publish_problems_are_still_explained():
    view = exam_view()
    view['exam_run']['stale'] = True
    assert not reply_to('please publish the exam schedule', view).get('action')
    view['exam_run'].update(stale=False, published=True)
    assert reply_to('please publish the exam schedule', view)['text'] == ['The latest exam timetable is already published.']


def test_teaching_publish_is_unchanged():
    view = exam_view(screen=False)
    view['run'].update(on_screen=True)
    view['screen'] = {'page': 'timetable', 'run_id': 'run-draft3'}
    for text in ('publish it', 'ممكن تنشر الجدول ده؟'):
        assert reply_to(text, view)['action']['what'] == 'teaching', text
    plain = {**VIEW, 'screen': {}, 'run': {**VIEW['run'], 'published': False, 'complete': True, 'on_screen': True}}
    assert answer(understand('publish it', plain, None), plain, False)['action']['what'] == 'teaching'


def test_the_local_model_path_answers_exam_publishing_without_the_model():
    def never(request):
        raise AssertionError('the local model must not be asked')
    settings = ('local', 'http://127.0.0.1:11434', 5)
    for text, expected in (('please publish the exam schedule', EN), ('ممكن تنشر جدول الامتحانات؟', AR)):
        reply = asyncio.run(converse(text, exam_view(), [], settings, app, transport=httpx.MockTransport(never)))
        assert reply['source'] == 'built-in' and reply['text'] == [expected]
        assert reply['action']['type'] == 'publish' and reply['action']['what'] == 'exams' and reply['action']['run_id'] == 'exam-mid1'


def test_chat_api_proposes_the_exam_on_screen_and_asks_between_several(environment):
    from app.models import ExamRun, Workspace
    client, factory = environment
    login(client)
    with factory.begin() as db:
        current = db.get(Workspace, 1).version
        for ident, name in (('exam-a', 'Business midterms'), ('exam-b', 'Business finals')):
            db.add(ExamRun(id=ident, name=name, input_version=current, snapshot={'settings': {'kind': 'midterm', 'use_halls': True}, 'halls': []},
                           result={'status': 'completed', 'assignments': []}))
    on_screen = client.post('/api/assistant', json={'text': 'please publish the exam schedule', 'previous': {}, 'screen': {'page': 'exams', 'run_id': 'exam-a'}}).json()
    assert on_screen['action'] == {'type': 'publish', 'what': 'exams', 'run_id': 'exam-a', 'label': 'Publish'}
    with factory() as db:
        assert db.get(ExamRun, 'exam-a').published_at is None  # only proposed; the admin confirms
    unclear = client.post('/api/assistant', json={'text': 'يرجى نشر جدول الامتحانات', 'previous': {}}).json()
    assert not unclear['action'] and {c['label'] for c in unclear['choices']} == {'Business midterms', 'Business finals'}
