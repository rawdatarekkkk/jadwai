"""Keep chat's direct HTTP calls aligned with the real website routes."""
import re
from pathlib import Path
from app.main import app


def test_chat_literal_endpoints_exist_in_openapi():
    source=(Path(__file__).resolve().parents[2]/'frontend/src/JaiChat.tsx').read_text()
    routes={(method.upper(),re.sub(r'\{[^}]+\}','{value}',path)) for path,methods in app.openapi()['paths'].items() for method in methods}
    calls=re.findall(r'\bapi(?:<[^\n]*?>)?\(\s*(["`])([^\n]*?)\1\s*(?:,\s*"(GET|POST|PUT|PATCH|DELETE)")?',source)
    checked=[]
    for _,path,method in calls:
        if not path.startswith('/') or path.startswith('//'):
            continue
        normalized=re.sub(r'\$\{[^}]+\}','{value}',path)
        assert any(verb == (method or 'GET') and re.fullmatch(re.escape(route).replace(re.escape('{value}'), '[^/]+'), '/api'+normalized) for verb,route in routes), (method or 'GET',path)
        checked.append(path)
    assert len(checked)>=20
