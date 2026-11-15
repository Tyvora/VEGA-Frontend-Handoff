import copy
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
import pytest
from jsonschema import Draft202012Validator
from user_input import SesameResolver, create_request

SCHEMA=json.loads((Path(__file__).parents[2]/'contracts/input_contract.json').read_text(encoding='utf-8-sig'))
VALIDATOR=Draft202012Validator(SCHEMA)

def response(name='Vega', body=''):
    return ('<Sesame><Target><name>'+name+'</name>'+body+'</Target></Sesame>').encode()

def resolver_xml(name='* alf Lyr', ra='279.234734787', dec='38.783688956'):
    return f'<Resolver name="S=Simbad"><oname>{name}</oname><jradeg>{ra}</jradeg><jdedeg>{dec}</jdedeg><refPos>2007A&amp;A...474..653V</refPos></Resolver>'

def setup_reply(monkeypatch, data):
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k: io.BytesIO(data))

@pytest.mark.parametrize('query', ['Vega','Alpha Lyrae'])
def test_names_and_alias(monkeypatch,tmp_path,query):
    setup_reply(monkeypatch,response(query,resolver_xml()))
    r=create_request('name',query,'sky_viewer',resolver=SesameResolver(cache_dir=tmp_path))
    assert r['canonical_name']=='* alf Lyr' and r['resolution_status']=='resolved'
    VALIDATOR.validate(r)

@pytest.mark.parametrize('body,status', [('<INFO> *** NNNothing found *** </INFO>','not_found'),('', 'resolver_error'),('<Resolver name="S=Simbad"><oname>Vega</oname></Resolver>','resolver_error'),(resolver_xml(''), 'resolver_error'),(resolver_xml(ra='nan'),'resolver_error')])
def test_unknown_and_incomplete(monkeypatch,tmp_path,body,status):
    setup_reply(monkeypatch,response(body=body))
    r=create_request('name','Vega','timeline',resolver=SesameResolver(cache_dir=tmp_path,retries=0))
    assert r['resolution_status']==status and r['ra_deg'] is None and r['dec_deg'] is None
    VALIDATOR.validate(r)
    if status=='resolver_error': assert not list(tmp_path.glob('*.json'))

def test_ambiguous(monkeypatch,tmp_path):
    setup_reply(monkeypatch,response(body=resolver_xml()+resolver_xml('Other', '2','3')))
    r=create_request('name','Vega','sky_viewer',resolver=SesameResolver(cache_dir=tmp_path))
    assert r['resolution_status']=='ambiguous' and len(r['candidates'])==2 and r['ra_deg'] is None
    VALIDATOR.validate(r)

@pytest.mark.parametrize('error,status', [(URLError('offline'),'service_unavailable'),(TimeoutError(),'service_unavailable'),(HTTPError('url',503,'bad',None,None),'service_unavailable'),(HTTPError('url',400,'bad',None,None),'resolver_error')])
def test_failures(monkeypatch,tmp_path,error,status):
    def fail(*a,**k): raise error
    monkeypatch.setattr('urllib.request.urlopen',fail)
    assert SesameResolver(cache_dir=tmp_path,retries=0).resolve('Vega')['resolution_status']==status
    assert not list(tmp_path.glob('*.json'))

@pytest.mark.parametrize('name,status', [('Mars','unsupported_target'),('','invalid_input'),('../etc','invalid_input')])
def test_invalid_and_moving(tmp_path,name,status):
    r=create_request('name',name,'sky_viewer',resolver=SesameResolver(cache_dir=tmp_path))
    assert r['resolution_status']==status and r['ra_deg'] is None
    VALIDATOR.validate(r)

def test_cache_ttls(monkeypatch,tmp_path):
    setup_reply(monkeypatch,response(body='<INFO> *** NNNothing found *** </INFO>'))
    resolver=SesameResolver(cache_dir=tmp_path)
    resolver.resolve('Vega')
    record=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert record['expires_at']-record['cached_at']==3600 and record['source'] and record['result']['retrieved_at']
    setup_reply(monkeypatch,response(body=resolver_xml()))
    resolver.resolve('Vega',force_refresh=True)
    record=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert record['expires_at']-record['cached_at']==604800

def test_contract_rejects_bad_requests():
    good=create_request('coordinates',{'ra':10,'dec':-20},'sky_viewer')
    VALIDATOR.validate(good)
    for change in ({'ra_deg':None},{'status':'needs_resolution'},{'resolution_status':'resolved'},{'extra':1},{'original_input':{'ra':10}},{'goal':'bad'}):
        bad={**copy.deepcopy(good),**change}
        assert list(VALIDATOR.iter_errors(bad)), change
    failed=create_request('name','Mars','sky_viewer')
    failed['ra_deg']=42
    assert list(VALIDATOR.iter_errors(failed))

def test_ambiguous_cache_ttl(monkeypatch,tmp_path):
    setup_reply(monkeypatch,response(body=resolver_xml()+resolver_xml('Other','2','3')))
    r=SesameResolver(cache_dir=tmp_path).resolve('Vega')
    record=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert r['resolution_status']=='ambiguous'
    assert record['expires_at']-record['cached_at']==3600

def test_contract_rejects_unresolved_success():
    class Fake:
        def resolve(self, name, force_refresh=False):
            return {'resolution_status':'resolved','canonical_name':'Vega','resolver_source':'mock'}
    bad=create_request('name','Vega','sky_viewer',resolver=Fake())
    assert list(VALIDATOR.iter_errors(bad))
