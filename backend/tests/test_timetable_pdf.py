"""Save as PDF: a real landscape page and a short descriptive name."""
import io
import pypdf
from app.timetable_pdf import compact_groups, initials, short_name, timetable_pdf
from test_scenarios import generated


def campus():
    return {"name": "GIU", "term": "Winter", "calendar": {"days": ["Sunday"], "start_hour": 8, "end_hour": 10, "period_minutes": 60, "timezone": "Africa/Cairo"}, "rules": [],
            "records": [{"id": "g7", "kind": "groups", "name": "Business Administration Core G7", "code": "BA5-G7", "year": 3, "major": "Business Administration", "size": 20}]}


def test_names_are_short_and_descriptive():
    assert initials("Finance, Banking & Accounting") == "FBA"
    assert short_name(campus(), {"group": "g7"}) == "BA Y3 G7 Schedule"
    assert short_name(campus(), {"year": "3", "major": "Business Administration"}) == "BA Y3 Schedule"
    assert short_name(campus(), None) == "Full Schedule"
    assert compact_groups([f"BA5-G{i}" for i in range(1, 11)]) == "BA5-G1–G10"


def test_pdf_page_is_landscape_and_not_rotated():
    reader = pypdf.PdfReader(io.BytesIO(timetable_pdf(campus(), [], "BA Y3 G7 Schedule", "test")))
    page = reader.pages[0]
    assert float(page.mediabox.width) > float(page.mediabox.height) and not page.get("/Rotate")
    assert reader.metadata.title == "BA Y3 G7 Schedule" and "Free" in page.extract_text()


def test_download_is_named_and_filtered_to_the_group(environment):
    client, factory = environment
    run = generated(client, factory)
    group = next(r for r in run['snapshot']['records'] if r['kind'] == 'groups')
    whole = client.get(f"/api/schedules/{run['id']}/timetable.pdf")
    assert whole.status_code == 200 and 'filename="Full Schedule.pdf"' in whole.headers['content-disposition']
    mine = client.get(f"/api/schedules/{run['id']}/timetable.pdf", params={'group': group['id']})
    assert mine.status_code == 200 and mine.headers['content-type'] == 'application/pdf'
    assert 'Schedule.pdf' in mine.headers['content-disposition']
    assert client.get(f"/api/schedules/{run['id']}/timetable.pdf", params={'group': 'nope'}).status_code == 422
