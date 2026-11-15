import json
from pathlib import Path
import pytest
from jsonschema import validate
from user_input import create_request, save_request, SesameResolver

class Fake:
    def resolve(self, name, force_refresh=False):
        return {'resolution_status':'resolved','ra_deg':279.2347,'dec_deg':38.7837,'canonical_name':'Vega','resolver_source':'mock'}

def test_coordinates_and_contract():
    r=create_request('coordinates',{'ra':279.2347,'dec':-38.7837},'sky_viewer')
    assert r['dec_deg']==pytest.approx(-38.7837)
    schema=json.loads((Path(__file__).parents[2]/'contracts/input_contract.json').read_text(encoding='utf-8-sig'))
    validate(r,schema)

def test_sexagesimal():
    r=create_request('coordinates',{'ra':'18h36m56.3s','dec':'+38°47′01″'},'timeline')
    assert r['ra_deg']==pytest.approx(279.234583333,abs=1e-7)
    assert r['dec_deg']==pytest.approx(38.783611111,abs=1e-7)

def test_ambiguous_units():
    with pytest.raises(ValueError): create_request('coordinates',{'ra':'18:36:56','dec':'+38:47:01'},'sky_viewer')

def test_name_preset_fov():
    r=create_request('name','Alpha Lyrae','discoveries', resolver=Fake())
    assert r['resolution_status']=='resolved' and r['target_name']=='Alpha Lyrae'
    p=create_request('preset','m31','timeline', fov_deg=0.3)
    assert p['fov_source']=='user' and p['fov_deg']==0.3 and p['region_shape']=='circle'

def test_persist_unique(tmp_path):
    r=create_request('preset','m31','sky_viewer')
    path=save_request(r,tmp_path)
    assert json.loads(path.read_text())['request_id']==r['request_id']
    with pytest.raises(FileExistsError): save_request(r,tmp_path)
    assert r['request_id'] != create_request('preset','m31','sky_viewer')['request_id']

def test_invalid_goal_and_solar():
    with pytest.raises(ValueError): create_request('preset','m31','bad')
    assert SesameResolver().resolve('Mars')['resolution_status']=='unsupported_target'

def test_network_failure(monkeypatch):
    import urllib.error
    def fail(*a,**k): raise urllib.error.URLError('offline')
    monkeypatch.setattr('urllib.request.urlopen',fail)
    assert SesameResolver(retries=0).resolve('Vega')['resolution_status']=='service_unavailable'
