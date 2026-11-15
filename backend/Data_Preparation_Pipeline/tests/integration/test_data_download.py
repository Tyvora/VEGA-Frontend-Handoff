import io,json,hashlib
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
import numpy as np
import pytest
import requests
from astropy.io import fits
from data_download import download_batch,Limits,build_url,load_catalog

@pytest.fixture
def inputs():
    product={'product_id':'id','observation_id':'obs','collection':'spherex_dr1','downloadable':True,'access_url':'https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/test.fits'}
    return {'schema_version':'1.0','products':[product]}, {'status':'completed','request_id':'test'}, {'request_id':'test','ra_deg':210.80227,'dec_deg':54.34895,'fov_deg':.1,'coordinate_frame':'icrs'}, {'request_id':'test','status':'accepted','errors':[]}

@pytest.fixture
def payload():
    out=io.BytesIO();fits.HDUList([fits.PrimaryHDU(),fits.ImageHDU(np.ones((3,3)),name='IMAGE')]).writeto(out)
    return out.getvalue()

class Response:
    status_code=200
    def __init__(self,data,html=False):self.data=data;self.headers={'Content-Length':str(len(data)),'Content-Type':'text/html' if html else 'application/fits'}
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def raise_for_status(self):
        if self.status_code>=400:raise requests.HTTPError('server error')
    def iter_content(self,*a):
        for i in range(0,len(self.data),1024):yield self.data[i:i+1024]
class Session:
    def __init__(self,response):self.response=response;self.calls=0
    def get(self,*a,**k):self.calls+=1;return self.response

def run(inputs,tmp_path,response,**kwargs):return download_batch(*inputs,['id'],root=tmp_path,session=Session(response),**kwargs)

def test_urls(inputs):
    product=inputs[0]['products'][0]
    url,params=build_url(product,inputs[2])
    assert parse_qs(urlsplit(url).query)['size']==['0.1deg']
    assert params['center']=='210.80227,54.34895deg'
    assert build_url(product,inputs[2],'full')==(product['access_url'],None)

@pytest.mark.parametrize('url',['http://irsa.ipac.caltech.edu/file','https://evil.example/file','https://irsa.ipac.caltech.edu@evil.example/fits','https://irsa.ipac.caltech.edu/other.fits',None])
def test_bad_urls(inputs,url):
    product=inputs[0]['products'][0];product['access_url']=url
    with pytest.raises(ValueError):build_url(product,inputs[2])

def test_success_manifest(inputs,payload,tmp_path):
    entries,manifest=run(inputs,tmp_path,Response(payload))
    e=entries[0];assert e['download_status']=='downloaded'
    assert e['sha256']==hashlib.sha256(payload).hexdigest()
    assert Path(e['local_file_path']).read_bytes()==payload
    assert json.loads(manifest.read_text())['entries']==entries
    assert e['extensions']==['PRIMARY','IMAGE']
    assert not list(tmp_path.rglob('*.part'))

@pytest.mark.parametrize('data,html',[(b'<html>error</html>',True),(b'not fits',False)])
def test_nonfits(inputs,tmp_path,data,html):
    entries,_=run(inputs,tmp_path,Response(data,html))
    assert entries[0]['download_status']=='failed' and not list(tmp_path.rglob('*.part'))

def test_truncated(inputs,payload,tmp_path):
    entries,_=run(inputs,tmp_path,Response(payload[:-100]))
    assert entries[0]['download_status']=='failed'

def test_partial_http_body(inputs,payload,tmp_path):
    response=Response(payload);response.headers['Content-Length']=str(len(payload)+1)
    assert run(inputs,tmp_path,response)[0][0]['download_status']=='failed'

@pytest.mark.parametrize('limits',[Limits(max_file_bytes=1),Limits(max_total_bytes=1)])
def test_size_limits(inputs,payload,tmp_path,limits):
    assert run(inputs,tmp_path,Response(payload),limits=limits)[0][0]['download_status']=='failed'

def test_ineligible(inputs,payload,tmp_path):
    inputs[0]['products'][0]['downloadable']=False
    assert run(inputs,tmp_path,Response(payload))[0][0]['download_status']=='failed'

def test_cancel(inputs,payload,tmp_path):
    assert run(inputs,tmp_path,Response(payload),cancelled=lambda:True)[0][0]['error_details']=='Cancelled'

def test_http_error(inputs,payload,tmp_path):
    response=Response(payload);response.status_code=503
    assert run(inputs,tmp_path,response)[0][0]['download_status']=='failed'

def test_retries(inputs,tmp_path,monkeypatch):
    class Fail:
        calls=0
        def get(self,*a,**k):self.calls+=1;raise requests.Timeout('timeout')
    session=Fail();monkeypatch.setattr('time.sleep',lambda _:None)
    entries,_=download_batch(*inputs,['id'],root=tmp_path,session=session)
    assert session.calls==2 and entries[0]['download_status']=='failed'

def test_batch_partial_and_unique(inputs,payload,tmp_path):
    bad=dict(inputs[0]['products'][0],product_id='bad',downloadable=False)
    inputs[0]['products'].append(bad);inputs[1]['status']='partial'
    entries,_=download_batch(*inputs,['id','bad'],root=tmp_path,session=Session(Response(payload)),limits=Limits(max_products=2))
    assert [e['download_status'] for e in entries]==['downloaded','failed']
    assert entries[0]['warnings']
    second,_=run(inputs,tmp_path,Response(payload))
    assert second[0]['local_file_path']!=entries[0]['local_file_path']

def test_atomic_existing(inputs,payload,tmp_path,monkeypatch):
    def exists(*a):raise FileExistsError('existing destination')
    monkeypatch.setattr('os.link',exists)
    assert run(inputs,tmp_path,Response(payload))[0][0]['download_status']=='failed'
    assert not list(tmp_path.rglob('*.part'))

def test_catalog_read(inputs,tmp_path):
    path=tmp_path/'catalog.json';path.write_text(json.dumps(inputs[0]))
    assert load_catalog(path)==inputs[0]
