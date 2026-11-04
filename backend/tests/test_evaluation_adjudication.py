from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_evaluation_portal import completed_pack
from test_workflows import login

def reviews(client):
 document=completed_pack();other=deepcopy(document)
 other['items'][0]['annotation']={'decision':'clarify','proposals':[],'clarifications':['unit-test-disagreement'],'unsupported':[]}
 ids=[]
 for reviewer,pack in [('reviewer-a',document),('reviewer-b',other)]:
  response=client.post('/api/evaluation/reviews',json={'request_key':str(uuid4()),'reviewer_id':reviewer,'annotated':pack})
  assert response.status_code==201,response.text
  ids.append(response.json()['id'])
 return ids,{'id':document['items'][0]['id'],'annotation':document['items'][0]['annotation'],'rationale':'Synthetic test fixture only; confirms that resolution records are separate.'}

def test_adjudication_is_idempotent_immutable_and_does_not_promote_gold(environment):
 client,factory=environment;login(client)
 original=client.get('/api/workspace').json()
 (first,second),resolution=reviews(client)
 body={'request_key':str(uuid4()),'first_review_id':first,'second_review_id':second,'adjudicator_id':'test-adjudicator','resolutions':[resolution]}
 response=client.post('/api/evaluation/adjudications',json=body)
 assert response.status_code==201,response.text
 result=response.json();assert result['items']==24 and result['release_promoted'] is False
 again=client.post('/api/evaluation/adjudications',json=body)
 assert again.json()['id']==result['id']
 changed={**body,'adjudicator_id':'other-adjudicator'}
 assert client.post('/api/evaluation/adjudications',json=changed).status_code==409
 summary=client.get('/api/evaluation').json()
 assert len(summary['adjudications'])==1 and summary['independently_adjudicated'] is False
 exported=client.get('/api/evaluation/adjudications/'+result['id']+'/export')
 assert exported.status_code==200 and 'attachment' in exported.headers['content-disposition']
 record=exported.json();assert len(record['decisions'])==24 and not record['release_promoted']
 assert len(record['review_record_sha256'])==2 and record['identity_verification']=='operator_declared_only'
 current=client.get('/api/workspace').json()
 assert current['version']==original['version'] and current['records']==original['records']
 for sql in ["UPDATE evaluation_adjudication SET adjudicator_id='modified'",'DELETE FROM evaluation_adjudication','TRUNCATE evaluation_adjudication']:
  with pytest.raises(DBAPIError):
   with factory.begin() as db:db.execute(text(sql))
 client.post('/api/auth/logout');login(client,'viewer@example.test')
 assert client.post('/api/evaluation/adjudications',json=body).status_code==403
 assert client.get('/api/evaluation/adjudications/'+result['id']+'/export').status_code==403

@pytest.mark.parametrize('corruption',['missing','duplicate','invalid','blank_rationale','same_adjudicator','same_review'])
def test_invalid_decisions_do_not_create_an_adjudication(environment,corruption):
 client,_=environment;login(client)
 (first,second),resolution=reviews(client)
 body={'request_key':str(uuid4()),'first_review_id':first,'second_review_id':second,'adjudicator_id':'test-adjudicator','resolutions':[resolution]}
 if corruption=='missing':body['resolutions']=[]
 elif corruption=='duplicate':body['resolutions']=[resolution,resolution]
 elif corruption=='invalid':resolution['annotation']={'decision':'ready','proposals':[],'clarifications':[],'unsupported':[]}
 elif corruption=='blank_rationale':resolution['rationale']='   '
 elif corruption=='same_adjudicator':body['adjudicator_id']='REVIEWER-A'
 else:body['second_review_id']=first
 response=client.post('/api/evaluation/adjudications',json=body)
 assert response.status_code==422,response.text
 assert client.get('/api/evaluation').json()['adjudications']==[]
