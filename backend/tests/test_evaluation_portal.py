from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from app.evaluation_portal import pack,BUNDLE
from evaluation.development import load_bundle

def completed_pack():
 document=pack();gold={r['id']:r['gold'] for r in load_bundle(BUNDLE)[2]}
 for item in document['items']:
  item['annotation']=deepcopy(gold[item['id']]);item['rationale']='Synthetic software test only; not human review.'
 return document

def test_evaluation_access_exports_and_append_only_reviews(environment):
 from test_workflows import login
 client,factory=environment
 assert client.get('/api/evaluation').status_code==401
 login(client)
 original=client.get('/api/workspace').json()
 summary=client.get('/api/evaluation').json()
 assert summary['counts']=={'cases':144,'families':36,'contexts':2}
 assert summary['review_protocol']=='single_admin_reviewer' and not summary['independent_review_claim']
 assert not summary['reviews'] and not summary['independently_adjudicated']
 exported=client.get('/api/evaluation/review-pack')
 assert exported.status_code==200 and 'attachment' in exported.headers['content-disposition']
 assert all(item['annotation'] is None and 'gold' not in item for item in exported.json()['items'])
 assert client.get('/api/evaluation/guide').status_code==200
 protocol=client.get('/api/evaluation/protocol')
 assert protocol.status_code==200 and 'single human reviewer' in protocol.text
 key=str(uuid4());body={'request_key':key,'reviewer_id':'test-reviewer','annotated':completed_pack()}
 first=client.post('/api/evaluation/reviews',json=body)
 assert first.status_code==201,first.text
 again=client.post('/api/evaluation/reviews',json=body)
 assert again.json()['id']==first.json()['id']
 assert len(client.get('/api/evaluation').json()['reviews'])==1
 conflict={**body,'reviewer_id':'different-reviewer'}
 assert client.post('/api/evaluation/reviews',json=conflict).status_code==409
 after=client.get('/api/workspace').json()
 assert after['version']==original['version'] and after['records']==original['records']
 ident=first.json()['id'];record=client.get('/api/evaluation/reviews/'+ident+'/export').json()
 assert record['reviewer_id']=='test-reviewer' and len(record['annotations'])==24 and not record['adjudicated']
 assert record['review_protocol']=='single-admin-review-v1' and record['reviewer_role']=='administrator'
 assert len(record['review_protocol_sha256'])==64
 for statement in ["UPDATE evaluation_review SET reviewer_id='modified'","DELETE FROM evaluation_review","TRUNCATE evaluation_review"]:
  with pytest.raises(DBAPIError):
   with factory.begin() as db:db.execute(text(statement))
 client.post('/api/auth/logout');login(client,'viewer@example.test')
 for url in ['/api/evaluation','/api/evaluation/review-pack','/api/evaluation/guide','/api/evaluation/protocol','/api/evaluation/reviews/'+ident+'/export']:
  assert client.get(url).status_code==403
 assert client.post('/api/evaluation/reviews',json=body).status_code==403

@pytest.mark.parametrize('corruption',['blank','missing','changed_text','wrong_manifest'])
def test_invalid_reviews_do_not_create_records(environment,corruption):
 from test_workflows import login
 client,_=environment;login(client)
 annotated=completed_pack()
 if corruption=='blank':annotated['items'][0]['annotation']=None
 elif corruption=='missing':annotated['items'].pop()
 elif corruption=='changed_text':annotated['items'][0]['text']='Changed text'
 else:annotated['manifest_sha256']='wrong'
 result=client.post('/api/evaluation/reviews',json={'request_key':str(uuid4()),'reviewer_id':'unit-test','annotated':annotated})
 assert result.status_code==422 and result.json()['detail']=='invalid_review'
 assert client.get('/api/evaluation').json()['reviews']==[]


def test_comparison_reports_disputes_without_exposing_gold_or_changing_inputs(environment):
 from test_workflows import login
 client,factory=environment;login(client)
 version=client.get('/api/workspace').json()['version']
 document=completed_pack()
 def submit(reviewer,annotations):
  response=client.post('/api/evaluation/reviews',json={'request_key':str(uuid4()),'reviewer_id':reviewer,'annotated':annotations})
  assert response.status_code==201,response.text
  return response.json()['id']
 first=submit('reviewer-a',document)
 different=deepcopy(document)
 different['items'][0]['annotation']={'decision':'clarify','proposals':[],'clarifications':['reviewer_disagreement'],'unsupported':[]}
 different['items'][0]['rationale']='Synthetic software disagreement fixture.'
 second=submit('reviewer-b',different)
 response=client.get(f'/api/evaluation/compare?first={first}&second={second}')
 assert response.status_code==200,response.text
 report=response.json()
 assert report['semantic_agreement']['items']==24 and report['semantic_agreement']['equal']==23
 assert len(report['disagreements'])==1 and not report['gold_included'] and not report['adjudicated']
 exported=client.get(f'/api/evaluation/compare?first={first}&second={second}&download=true')
 assert exported.status_code==200 and 'attachment' in exported.headers['content-disposition']
 assert exported.json()==report
 disputed=report['disagreements'][0]
 assert disputed['text']==document['items'][0]['text']
 assert disputed['first_annotation']==document['items'][0]['annotation']
 assert 'gold' not in disputed and 'draft_gold_sha256' not in disputed
 assert client.get('/api/workspace').json()['version']==version
 assert client.get(f'/api/evaluation/compare?first={first}&second={first}').status_code==422
 same_reviewer=submit('reviewer-a',different)
 assert client.get(f'/api/evaluation/compare?first={first}&second={same_reviewer}').status_code==422
 assert client.get(f'/api/evaluation/compare?first={first}&second={uuid4()}').status_code==404
 client.post('/api/auth/logout');login(client,'viewer@example.test')
 assert client.get(f'/api/evaluation/compare?first={first}&second={second}').status_code==403
