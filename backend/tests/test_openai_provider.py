import asyncio
import json
import pytest
import httpx
from app.extraction import ExtractionRequest, extract_candidate
from app.openai_provider import OpenAIProvider, MODEL, PROMPT_VERSION, output_schema


def request():
    return ExtractionRequest.create('مش عايز محاضرات السبت', {'calendar':{'days':['Saturday']}},23,PROMPT_VERSION,'proposal-contract-v1')


def run(handler):
    return asyncio.run(extract_candidate(OpenAIProvider('unit-test-not-a-real-key',transport=httpx.MockTransport(handler)),request()))


def response(**changes):
    value={'id':'resp_test','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"decision":"clarify","proposals":[],"clarifications":["which_hours"],"unsupported":[]}'}]}],'usage':{'input_tokens':123,'output_tokens':45}}
    value.update(changes);return value


def test_exact_model_structured_schema_no_storage_and_observed_usage():
    def handler(req):
        assert str(req.url)=='https://api.openai.com/v1/responses'
        body=json.loads(req.content)
        assert body['model']==MODEL=='gpt-5.4-mini' and body['store'] is False
        assert body['text']['format']['strict'] and body['text']['format']['type']=='json_schema'
        assert 'مش عايز' in body['input']
        assert 'Authorization' not in body and 'api_key' not in body
        return httpx.Response(200,json=response())
    result=run(handler)
    assert result.status=='candidate' and result.requires_human_approval
    assert (result.response_id,result.input_tokens,result.output_tokens)==('resp_test',123,45)


@pytest.mark.parametrize('code,status',[(401,'provider_error'),(429,'provider_unavailable'),(503,'provider_unavailable'),(302,'provider_error')])
def test_errors_do_not_expose_provider_body(code,status):
    result=run(lambda _:httpx.Response(code,json={'error':'private provider message'}))
    assert result.status==status and result.candidate_json is None
    assert 'private provider message' not in repr(result)


@pytest.mark.parametrize('data,status',[
    (response(status='incomplete'),'incomplete'),
    (response(output=[{'type':'message','content':[{'type':'refusal','refusal':'private refusal'}]}]),'refused'),
    (response(output=[]),'invalid_response'),
    (response(usage={'input_tokens':-1}),'invalid_response'),
    (response(id={'invalid':'identity'}),'invalid_response'),
    (response(usage=['invalid']),'invalid_response'),
])
def test_incomplete_refusal_missing_output_and_bad_usage(data,status):
    result=run(lambda _:httpx.Response(200,json=data))
    assert result.status==status and result.candidate_json is None


def test_disabled_or_missing_key_never_constructs_live_provider(monkeypatch):
    monkeypatch.delenv('JADWAI_AI_ENABLED',raising=False)
    monkeypatch.setenv('OPENAI_API_KEY','fake')
    with pytest.raises(ValueError):OpenAIProvider.configured()
    monkeypatch.setenv('JADWAI_AI_ENABLED','true');monkeypatch.delenv('OPENAI_API_KEY')
    with pytest.raises(ValueError):OpenAIProvider.configured()


def test_all_schema_objects_are_closed_and_all_properties_required():
    def visit(node):
        if isinstance(node,dict):
            assert 'default' not in node
            if node.get('type')=='object':
                assert node['additionalProperties'] is False
                assert set(node['required'])==set(node['properties'])
            for value in node.values():visit(value)
        elif isinstance(node,list):
            for value in node:visit(value)
    visit(output_schema())
