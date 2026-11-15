import copy
import math
import json
import pytest
from user_input import create_request
from request_validation import validate_request, save_report, ValidationSettings

@pytest.fixture
def sample(): return create_request('coordinates',{'ra':10,'dec':20},'sky_viewer')

def test_accept(sample):
    report, ref=validate_request(sample)
    assert report['status']=='accepted' and ref is sample

@pytest.mark.parametrize('field,value', [('ra_deg',360),('ra_deg',-1),('dec_deg',91),('dec_deg',-91),('fov_deg',0.0009),('fov_deg',1.01),('ra_deg',float('nan')),('dec_deg',float('inf')),('fov_deg',float('-inf')),('goal','bad'),('coordinate_frame','galactic'),('schema_version','2')])
def test_reject(sample,field,value):
    sample[field]=value
    before=copy.deepcopy(sample)
    report,ref=validate_request(sample)
    assert report['status']=='rejected' and ref is None and sample==before

@pytest.mark.parametrize('ra,dec,fov',[(359.999999,90,.001),(0,-90,1.0)])
def test_boundaries(sample,ra,dec,fov):
    sample.update(ra_deg=ra,dec_deg=dec,fov_deg=fov)
    assert validate_request(sample)[0]['status']=='accepted'

def test_missing_and_status(sample):
    del sample['goal']
    assert validate_request(sample)[0]['status']=='rejected'
    sample['goal']='sky_viewer'; sample['resolution_status']='not_found'
    assert validate_request(sample)[0]['status']=='rejected'

def test_preset_and_name():
    assert validate_request(create_request('preset','m31','timeline'))[0]['status']=='accepted'
    class Resolver:
        def resolve(self,name,force_refresh=False): return {'resolution_status':'resolved','canonical_name':'Vega','resolver_source':'mock','ra_deg':279.2,'dec_deg':38.7}
    assert validate_request(create_request('name','Vega','discoveries',resolver=Resolver()))[0]['status']=='accepted'

def test_save(sample,tmp_path):
    report,_=validate_request(sample)
    path=save_report(report,tmp_path)
    assert json.loads(path.read_text())==report and save_report(report,tmp_path)!=path

def test_settings(sample):
    sample['fov_deg']=2
    assert validate_request(sample,ValidationSettings(max_fov_deg=2))[0]['status']=='accepted'

