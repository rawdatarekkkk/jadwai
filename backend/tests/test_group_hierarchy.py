import pytest
from test_workflows import login,version


def test_group_hierarchy_roundtrips_and_changes_versions(environment):
    client,_=environment;login(client)
    before=client.get('/api/workspace').json()['version']
    response=client.post('/api/records/groups',headers=version(client),json={'name':'Group A','code':'G1','size':30,'year':2,'major':'Computer Science'})
    assert response.status_code==201
    ident=response.json()['id']
    group=next(r for r in client.get('/api/workspace').json()['records'] if r['id']==ident)
    assert group['year']==2 and group['major']=='Computer Science'
    assert client.get('/api/workspace').json()['version']==before+1
    assert client.put('/api/records/groups/'+ident,headers=version(client),json={'name':'Group A','code':'G1','size':30,'year':3,'major':'Software Engineering'}).status_code==200
    changed=next(r for r in client.get('/api/workspace').json()['records'] if r['id']==ident)
    assert changed['year']==3 and changed['major']=='Software Engineering'

@pytest.mark.parametrize('fields',[{'year':0},{'year':13},{'year':True},{'year':'2'},{'year':2,'major':'   '},{'major':'CS'}])
def test_invalid_classification_is_rejected(environment,fields):
    client,_=environment;login(client)
    assert client.post('/api/records/groups',headers=version(client),json={'name':'G','code':'G','size':20,**fields}).status_code==422


def test_classified_csv_and_legacy_csv_remain_supported(environment):
    client,_=environment;login(client)
    for content in ['name,code,size,year,major\nA,A,25,1,Computer Science\nB,B,30,1,computer science\n','name,code,size\nLegacy,L,20\n']:
        assert client.post('/api/imports/groups/commit',headers=version(client),json={'csv':content}).status_code==201
    groups={r['code']:r for r in client.get('/api/workspace').json()['records'] if r['kind']=='groups'}
    assert groups['A']['major']==groups['B']['major']=='Computer Science'
    assert groups['L']['year'] is None and groups['L']['major'] is None
