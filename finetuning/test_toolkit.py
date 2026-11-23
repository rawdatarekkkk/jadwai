"""Dataset integrity, review gate and real frame compilation checks."""
import asyncio
import json
import shutil
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parent))
import toolkit
from app.teaching_language import compile_frame


def test_families_and_prompts_do_not_cross_splits():
 rows=toolkit.load()
 train={r['family'] for r in rows if r['split']=='train'}
 test={r['family'] for r in rows if r['split']=='test'}
 assert train and test and not train.intersection(test)
 assert len(rows)==315
 assert all('fictional draft' in r['provenance'] for r in rows)


def test_unreviewed_labels_cannot_be_exported(tmp_path):
 with pytest.raises(ValueError,match='No approved examples'):
  toolkit.export(toolkit.load(),toolkit.BASE/'data/review-template.json',tmp_path/'export')
 assert not (tmp_path/'export/train.jsonl').exists()


def test_approved_review_is_bound_to_exact_family_hash(tmp_path):
 rows=toolkit.load();review=json.loads((toolkit.BASE/'data/review-template.json').read_text())
 item=next(r for r in review['reviews'] if r['family']=='soft-first-lecture')
 item.update(approved=True,reviewer='test-fixture-only',rationale='Software gate test; not a human review.')
 p=tmp_path/'fixture-review.json';p.write_text(json.dumps(review))
 assert len(toolkit.reviewed(rows,p,'train'))==3
 item['family_sha256']='tampered';p.write_text(json.dumps(review))
 with pytest.raises(ValueError,match='No approved examples'):toolkit.reviewed(rows,p,'train')


def test_changed_dataset_is_rejected(tmp_path,monkeypatch):
 shutil.copytree(toolkit.BASE/'data',tmp_path/'data')
 with (tmp_path/'data/train.jsonl').open('a') as f:f.write('\n')
 monkeypatch.setattr(toolkit,'BASE',tmp_path)
 with pytest.raises(ValueError,match='Dataset changed'):toolkit.load()


def test_frames_compile_with_real_backend_without_widening_types():
 calendar={'days':['Sunday','Monday','Tuesday','Wednesday','Thursday'],'start_hour':8,'end_hour':18,'period_minutes':90}
 for row in toolkit.load():
  if row['task']!='frame':continue
  target=row['target'];text=json.loads(row['messages'][-1]['content'])['requirement']
  result=compile_frame(target,text,calendar)
  if target['kind']=='other':assert result is None
  elif target['kind']=='clarify':assert result['decision']=='clarify'
  else:
   assert result['decision']=='ready'
   assert all(p['data']['strength']==target['strength'] and p['data']['params']['activity_types']==target['activity_types'] for p in result['proposals'])


def test_multiturn_history_is_present_for_schedule_and_unknown_name_cases():
 rows=toolkit.load()
 for family in ('exam-pdf-context','exam-publish-context','unknown-cs','correction-no-action'):
  row=next(r for r in rows if r['family']==family)
  assert any(m['role']=='assistant' for m in row['messages'][:-1])


def test_review_pack_covers_every_family():
 text=(toolkit.BASE/'data/REVIEW.md').read_text()
 for family in {r['family'] for r in toolkit.load()}:assert f'## {family}\n' in text


def test_conversation_prompts_match_the_production_chat_exactly():
 """Each conversation row must be byte-for-byte what assistant_capabilities.converse sends to Ollama."""
 import httpx
 from conversations import view
 from app.assistant_capabilities import converse
 from app.main import app
 for row in (r for r in toolkit.load() if r['task']=='conversation'):
  sent=[]
  def reply(request):
   sent.append(json.loads(request.content))
   return httpx.Response(200,json={'done':True,'message':{'content':json.dumps({'operation':'','reply':'ok'})}})
  payload=json.loads(row['messages'][-1]['content']);history=row['messages'][1:-1]
  out=asyncio.run(converse(payload['message'],view(row['scenario']),history,('m','http://ollama.test',5),app,transport=httpx.MockTransport(reply),pending=payload['pending']))
  assert out=={'text':['ok'],'conversation':True},row['id']
  assert sent[0]['messages']==row['messages'],row['id']
  assert sent[0]['format']==row['schema'],row['id']


def test_conversation_replies_are_grounded_and_in_the_users_language():
 rows=[r for r in toolkit.load() if r['task']=='conversation']
 assert len(rows)==216 and {r['language'] for r in rows}=={'en','ar'}
 for r in rows:
  checks=toolkit.reply_checks(r,r['target'])
  assert r['target']['operation']=='' and checks['within_80_words'] and checks['language_match'] and not checks['exposes_internal'],r['id']


def test_blind_sheet_hides_which_model_wrote_each_reply(tmp_path):
 rows=[r for r in toolkit.load() if r['task']=='conversation'][:2]
 runs=[]
 for name in ('base','tuned'):
  p=tmp_path/f'{name}.jsonl';p.write_text(''.join(json.dumps({'id':r['id'],'prediction':{'reply':f'{name} says hi'}})+'\n' for r in rows));runs.append(str(p))
 out=tmp_path/'sheet.md'
 toolkit.sheet(type('A',(),{'runs':runs,'output':str(out),'seed':1})())
 text=out.read_text()
 assert 'base says hi' in text and 'tuned says hi' in text and 'base.jsonl' not in text
 assert json.loads(out.with_suffix('.key.json').read_text())


def test_replies_rely_on_guide_entries_present_in_their_prompt():
 from app.assistant_guide import GUIDE
 from conversations import GUIDE_TOPICS
 bodies={t:b for t,_,b in GUIDE}
 rows=[r for r in toolkit.load() if r['task']=='conversation']
 assert set(GUIDE_TOPICS)<={r['family'] for r in rows} and {t for ts in GUIDE_TOPICS.values() for t in ts}<=set(bodies)
 for r in rows:
  given=json.loads(r['messages'][-1]['content'])['facts']['guide']
  assert all(bodies[t] in given for t in GUIDE_TOPICS.get(r['family'],[])),r['id']
 unsure=[r for r in rows if r['family'].startswith('not-sure-')]
 assert unsure and all(r['target']['reply'].startswith(('I am not sure','مش متأكد')) for r in unsure)
