from app.assistant_capabilities import facts
from app.assistant_guide import GUIDE, guide


def topics(text):
    bodies = {body: topic for topic, _, body in GUIDE}
    return [bodies[b] for b in guide(text)]


def test_relevant_entries_in_english_and_egyptian_arabic():
    assert topics('does my data go to the cloud?') == ['privacy']
    assert topics('why does generating take so long?')[0] == 'solver-time'
    assert topics('ليه التوليد بياخد وقت طويل؟')[0] == 'solver-time'
    assert topics('what will students see after I publish?')[0] == 'portals'
    assert topics('النظام بيختار المعمل للسكشن إزاي؟') == ['rooms']
    assert topics('write me a poem about exams')[0] == 'scope'


def test_word_boundaries_and_small_talk():
    assert 'instructors' not in topics('is my data stored safely?')  # "ta" inside "data"
    assert topics('hi') == []
    assert len(guide('publish the exam draft after I check room capacity and the TA workload')) <= 3


def test_entries_reach_the_model_prompt():
    view = {'_message': 'does my data go to the cloud?', 'records': [], 'calendar': {}, 'sessions': []}
    assert facts(view)['guide'] == guide('does my data go to the cloud?')


def test_entries_never_expose_internal_paths():
    for _, _, body in GUIDE:
        assert '/api/' not in body and len(body.split()) <= 80


def test_repeated_sentences_are_removed():
    from app.assistant_capabilities import clean_reply
    assert clean_reply('A is fine. B is slow. A is fine. B is slow. C?') == 'A is fine. B is slow. C?'
    assert clean_reply('المسودة الأولى أسرع. المسودة الأولى أسرع. تمام؟') == 'المسودة الأولى أسرع. تمام؟'
    assert clean_reply('Default is 240.5 seconds. Dr. Karim Adel teaches it.') == 'Default is 240.5 seconds. Dr. Karim Adel teaches it.'


def test_cut_off_reply_is_rescued_as_conversation_only():
    from app.assistant_capabilities import salvage_reply
    looping = '{"reply": "Nobody sees drafts. Nobody sees drafts. Nobody sees dr'
    assert salvage_reply(looping) == {'reply': 'Nobody sees drafts.', 'operation': ''}
    assert salvage_reply('{"reply": "no complete sentence') is None
    assert salvage_reply('not json at all') is None


def test_new_topics_and_formal_arabic():
    assert 'unknown-features' in topics('will students get an email when I publish?')
    assert 'solver' in topics('how does JadwAI actually make the schedule?')
    assert 'periods' in topics('how can a 3-hour lab fit if periods are 90 minutes?')
    assert 'advising' in topics('كيف يتم التعامل مع طالب يعيد مادة مع مجموعة أخرى؟')
    assert 'deleting' in topics('ماذا يحدث إذا حذفت القاعة H12؟')
    assert 'instructors' not in topics('مين كمان بيحضر المحاضرة دي؟')  # "محاضرة" (lecture) is not an instructor
