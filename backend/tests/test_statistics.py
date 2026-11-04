from uuid import uuid4
import pytest
from app.statistics import build_statistics,html_report
from app.validation import validate_schedule
from app.schedule_worker import process_one
from app.models import ScheduleRun
from test_schedules import example,setup_data,start
from test_workflows import login,version


def measured():
    snap=example();snap.update(input_version=1,name='CS',term='Fall')
    snap['records'][0].update(name='T',code='T');snap['records'][1].update(name='U',code='U')
    for r in snap['records']:r.setdefault('name',r['id']);r.setdefault('code',r['id'])
    snap['records'].append({'id':'v','kind':'instructors','name':'Unused','code':'V'})
    snap['records'][-2]['eligible_instructors']=['u']
    snap['rules']=[{'id':'p','title':'T mornings','status':'approved','type':'preferred_period','instructor_id':'t','day':'Sunday','start_hour':8,'end_hour':9}, {'id':'q','title':'Unused preference','status':'approved','type':'preferred_period','instructor_id':'v','day':'Sunday','start_hour':8,'end_hour':9}]
    rows=[{'activity_id':'a','occurrence':0,'instructor_id':'t','room_id':'r','day':'Sunday','start_minute':480,'end_minute':540},{'activity_id':'a','occurrence':1,'instructor_id':'t','room_id':'r','day':'Monday','start_minute':480,'end_minute':540},{'activity_id':'b','occurrence':0,'instructor_id':'u','room_id':'r','day':'Monday','start_minute':540,'end_minute':630}]
    report=validate_schedule(snap,rows);assert report['passed']
    return snap,{'status':'completed','assignments':rows,'validation':report,'optimal':True,'preference_penalty':1,'solver_seconds':0.1}


def test_statistics_match_known_manual_counts():
    snap,result=measured();s=build_statistics(snap,result)
    assert s['coverage']['assignment_percent']==100
    assert s['preferences']['applicable_sessions']==2
    assert s['preferences']['satisfied_sessions']==1
    assert s['preferences']['unsatisfied_sessions']==1
    assert s['preferences']['satisfaction_percent']==50
    assert s['preferences']['partially_satisfied_rules']==1
    assert s['preferences']['not_applicable_rules']==1
    assert s['utilization']['room_time_percent']==43.75
    assert s['utilization']['occupied_room_seat_percent']==80
    assert s['utilization']['scheduled_teaching_minutes']==210
    assert all(v==0 for v in s['validation']['conflicts'].values())


def test_breaks_are_excluded_and_unused_preferences_not_counted_as_success():
    snap,result=measured();snap['calendar']['teaching_periods']=[{'start':480,'end':540},{'start':600,'end':660}]
    stats=build_statistics(snap,result)
    assert stats['utilization']['available_teaching_minutes_per_room']==240
    snap['rules']=[]
    stats=build_statistics(snap,result)
    assert stats['preferences']['satisfaction_percent'] is None
    assert stats['preferences']['fully_satisfied_rules']==0


def test_report_escapes_hostile_text_and_preserves_unicode():
    snap,result=measured();snap['name']='<script>alert(1)</script> العربية'
    text=html_report('run',snap,build_statistics(snap,result),True)
    assert '<script>' not in text and '&lt;script&gt;' in text
    assert text.count('<h2>Saved inputs</h2>')==1
    assert 'العربية' in text and 'Inputs have changed' in text
    assert 'Weekly workload limits' in text


def test_report_is_saved_and_downloadable_without_changing_inputs(environment):
    client,factory=environment;login(client);setup_data(client,factory)
    ident=start(client).json()['id']
    assert client.get(f'/api/schedules/{ident}/statistics').status_code==409
    assert process_one(factory)
    with factory() as db:assert db.get(ScheduleRun,ident).result['statistics']['report_version']==1
    before=client.get('/api/workspace').json()
    pdf=client.get(f'/api/schedules/{ident}/statistics')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF-')
    assert pdf.headers['content-type']=='application/pdf'
    assert 'Statistics-Report_Full-Schedule_Draft' in pdf.headers['content-disposition']
    assert '.pdf' in pdf.headers['content-disposition']
    assert "filename*=UTF-8''" in pdf.headers['content-disposition']
    html=client.get(f'/api/schedules/{ident}/statistics?format=html')
    assert html.status_code==200 and 'attachment' in html.headers['content-disposition']
    assert 'Schedule statistics' in html.text and 'DRAFT' in html.text
    data=client.get(f'/api/schedules/{ident}/statistics?format=json').json()
    assert data['statistics']['coverage']['scheduled_sessions']==2
    assert not data['stale']
    assert client.get('/api/workspace').json()['version']==before['version']
    assert client.get(f'/api/schedules/{ident}/statistics?format=unknown').status_code==422
    client.post('/api/records/groups',headers=version(client),json={'name':'New','code':'NEW','size':10})
    assert client.get(f'/api/schedules/{ident}/statistics?format=json').json()['stale']
    login(client,'viewer@example.test')
    assert client.get(f'/api/schedules/{ident}/statistics').status_code==403


def test_pdf_summary_is_one_page_with_charts_and_honest_denominators():
    from io import BytesIO
    from pypdf import PdfReader
    from app.statistics_pdf import pdf_report
    snap,result=measured()
    stats=build_statistics(snap,result)
    pdf=pdf_report('known-run',snap,stats,True)
    reader=PdfReader(BytesIO(pdf))
    assert len(reader.pages)==1
    text=reader.pages[0].extract_text()
    for expected in ('Your timetable at a glance','3 / 3','50.0%','43.8%','80.0%', 'Inputs have changed', 'not publication-ready', 'Room time', 'known-run'):
        assert expected in text
    assert '1 / 2 applicable sessions' in text
    assert len(reader.pages[0].get_contents().get_data()) > 1000
    snap['rules']=[]
    text=PdfReader(BytesIO(pdf_report('none',snap,build_statistics(snap,result),False))).pages[0].extract_text()
    assert 'No applicable preferences' in text and 'N/A' in text


def test_export_names_are_safe_and_preserve_unicode():
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from app.export_names import report_disposition
    row=SimpleNamespace(snapshot={'term':'Fall / 2026', 'name':'علوم الحاسب\r\n"/test'}, input_version=11, id='12345678-aaaa', created_at=datetime(2026,10,18,tzinfo=timezone.utc))
    header=report_disposition(row,'pdf')
    assert '\r' not in header and '\n' not in header
    assert 'Fall-2026' in header and 'v11_2026-10-18_12345678.pdf' in header
    assert '%D8' in header
