import copy
from pathlib import Path
import pytest
from user_input import create_request
from request_validation import validate_request
from archive_search import search,SIASettings
from archive_search.sia import COLLECTIONS,parameters,decode,map_product

@pytest.fixture
def req():
    r=create_request('coordinates',{'ra':10,'dec':20},'sky_viewer')
    return r,validate_request(r)[0]

def row(collection,identity='id',url='https://irsa.ipac.caltech.edu/file.fits'):
    return {'obs_collection':collection,'obs_publisher_did':identity,'access_url':url,'calib_level':2,'dataproduct_type':'image','access_format':'image/fits','energy_bandpassname':'SPHEREx-D2','obs_id':'obs'}

class Client:
    def __init__(self,status='OK',rows=True,fail=None): self.calls=[]; self.status=status; self.rows=rows; self.fail=fail
    def query(self,p):
        self.calls.append(p)
        if self.fail: raise self.fail
        return ([row(p['COLLECTION'])] if self.rows else []),self.status,{}

def test_four_collections_and_eligibility(req):
    client=Client(); catalog,report=search(*req,client=client)
    assert len(client.calls)==4 and {p['COLLECTION'] for p in client.calls}==set(COLLECTIONS)
    assert all(p['DPTYPE']=='image' and p['CALIB']==2 and p['POS']=='CIRCLE 10 20 0.05' for p in client.calls)
    assert report['status']=='completed' and len(catalog['products'])==1
    assert catalog['products'][0]['downloadable']

@pytest.mark.parametrize('status,rows,expected',[('OK',False,'no_results'),('OVERFLOW',True,'partial'),('OK',True,'completed')])
def test_status(req,status,rows,expected):
    assert search(*req,client=Client(status,rows))[1]['status']==expected

def test_interrupted(req):
    client=Client(fail=TimeoutError('offline'))
    assert search(*req,client=client)[1]['status']=='failed'

@pytest.mark.parametrize('field,value',[('calib_level',1),('dataproduct_type','cube'),('access_url','https://evil.example/file'),('obs_publisher_did',None),('access_format','text/plain')])
def test_ineligible(field,value):
    r=row('spherex_dr1');r[field]=value
    assert not map_product(r,'spherex_dr1')['downloadable']

def test_saved_real_votable():
    path=Path(__file__).parents[2]/'data/search_results/access-0b265b5e-86cc-4d18-bfa3-6368325087e9/sia2_diagnostic.xml'
    rows,status,units=decode(path.read_bytes())
    assert status=='OVERFLOW' and len(rows)==2 and 'access_url' in rows[0]
    assert units['s_ra']=='deg'

@pytest.mark.parametrize('raw',[b'',b'<VOTABLE/>',b'<VOTABLE><RESOURCE><INFO name="QUERY_STATUS" value="ERROR">bad</INFO></RESOURCE></VOTABLE>'])
def test_incomplete(raw):
    with pytest.raises(Exception): decode(raw)

def test_distinct_products(req):
    class Distinct:
        def query(self,p):
            a=row(p['COLLECTION'],'id1');b=row(p['COLLECTION'],'id2');b['energy_bandpassname']='SPHEREx-D3';b['t_min']=60000
            return [a,a,b],'OK',{}
    products,report=search(*req,client=Distinct(),collections=['spherex_dr1'])
    assert len(products['products'])==2

def test_missing_partition(req):
    class Missing:
        def query(self,p):
            if p['COLLECTION']=='spherex_qr3':raise TimeoutError('missing collection')
            return [],'OK',{}
    assert search(*req,client=Missing())[1]['status']=='partial'
