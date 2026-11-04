from test_workflows import login, version


def test_course_eligibility_filters_are_enforced_and_updates_preserve_activities(environment):
    client, factory = environment
    login(client)
    def create(kind, data):
        response = client.post('/api/records/'+kind, headers=version(client), json=data)
        assert response.status_code == 201, response.text
        return response.json()['id']
    group = create('groups', {'name':'Year 1', 'code':'Y1', 'size':20})
    other_group = create('groups', {'name':'Year 2', 'code':'Y2', 'size':20})
    tutor = create('instructors', {'name':'Tutor','code':'TUT','department':'CS'})
    setup = {'name':'Algorithms','code':'ALG','eligibility':{'lecture':['teacher'],'tutorial':[tutor],'lab':[]},'group_ids':[group]}
    response = client.post('/api/course-catalog', headers=version(client), json=setup)
    assert response.status_code == 201, response.text
    course = response.json()['id']
    from app.models import CourseCatalog
    with factory.begin() as db:
        db.get(CourseCatalog, course).source_info = {'program_semesters':[{'faculty_section':'INFORMATICS','program_or_cohort':'Computer Science','semester':3}]}
    body = {'name':'ignored supplied name','code':'ALG-L','course_id':course,'activity_type':'lecture','sessions':1,'duration':60,'eligible_instructors':[tutor],'group_ids':[group]}
    assert client.post('/api/records/courses',headers=version(client),json=body).status_code == 422
    body.update(eligible_instructors=['teacher'],group_ids=[other_group])
    assert client.post('/api/records/courses',headers=version(client),json=body).status_code == 422
    body['group_ids']=[group]
    create('courses', body)
    record = next(r for r in client.get('/api/workspace').json()['records'] if r['code']=='ALG-L')
    assert record['name']=='Algorithms' and record['course_id']==course
    setup['eligibility']['lecture']=[]
    assert client.put('/api/course-catalog/'+course,headers=version(client),json=setup).status_code == 409
    assert client.delete('/api/records/instructors/'+tutor, headers=version(client)).status_code == 409
    setup['eligibility']['lecture']=['teacher'];setup['name']='Advanced Algorithms'
    assert client.put('/api/course-catalog/'+course,headers=version(client),json=setup).status_code == 200
    assert next(r for r in client.get('/api/workspace').json()['records'] if r['code']=='ALG-L')['name']=='Advanced Algorithms'
    assert client.get('/api/workspace').json()['course_catalog'][0]['source_info']['program_semesters'][0]['semester']==3
    client.post('/api/auth/logout')
    login(client,'viewer@example.test')
    assert client.post('/api/course-catalog',headers=version(client),json=setup).status_code==403
