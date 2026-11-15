"""Offline nine-interface orchestration tests; fake artifacts are explicitly synthetic."""
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from orchestrator import Services,WorkflowLimits,run_pipeline
from orchestrator.state import read,write,sha
from orchestrator.runner import checked_download

@pytest.fixture
def mocked(tmp_path):
    services=Services();calls=[];control={'fail_product':None,'interrupt':None}
    def save(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj));return path
    def search(request,acceptance,**kw):
        calls.append(('search',None))
        products=[{'product_id':'p'+str(i),'observation_id':'obs'+str(i),'observation_start':60000+i,'detector':'D3','downloadable':True,'collection':'spherex_dr1','access_url':f'https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/{i}.fits'} for i in (1,2,3)]
        return {'schema_version':'1.0','products':products},{'request_id':request['request_id'],'status':'completed','warnings':[]}
    def download(catalog,report,request,acceptance,ids,**kw):
        pid=ids[0];calls.append(('download',pid));product=next(p for p in catalog['products'] if p['product_id']==pid)
        n=sum(c[0]=='download' for c in calls);file=tmp_path/'data/cutouts'/f'{pid}-{n}.fits';file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'SYNTHETIC-TRANSPORT-FIXTURE')
        _,params=services.build_url(product,request)
        entry={'request_id':request['request_id'],'product_id':pid,'observation_id':product['observation_id'],'collection':product['collection'],'source_url':product['access_url'],'cutout_parameters':params,'download_mode':'cutout','download_status':'downloaded','local_file_path':str(file),'sha256':sha(file),'file_size':file.stat().st_size}
        path=save(tmp_path/'data/manifests'/f'download-{pid}-{n}.json',{'request_id':request['request_id'],'entries':[entry],'network_bytes':file.stat().st_size})
        return [entry],path
    def extract(manifest,pid,**kw):
        calls.append(('extract',pid))
        if control['interrupt']==pid:raise KeyboardInterrupt('synthetic interrupted process')
        entry=read(manifest)['entries'][0];folder=tmp_path/'data/extractions'/f'{pid}-{len(calls)}'
        save(folder/'metadata.json',{'request_id':entry['request_id'],'product_id':pid,'observation_id':entry['observation_id'],'source_fits_path':entry['local_file_path']})
        report={'status':'completed','errors':[]};save(folder/'report.json',report)
        return report,folder
    def technical(folder,**kw):
        meta=read(Path(folder)/'metadata.json');pid=meta['product_id'];calls.append(('technical',pid))
        if control['fail_product']==pid:raise ValueError('synthetic product failure')
        report={**meta,'overall_technical_status':'passed','errors':[]}
        return report,save(tmp_path/'data/validation'/f'{pid}-{len(calls)}.json',report)
    def quality(folder,tech,**kw):
        meta=read(Path(folder)/'metadata.json');calls.append(('quality',meta['product_id']))
        out=tmp_path/'data/quality'/f"{meta['product_id']}-{len(calls)}";report={**meta,'quality_status':'passed','errors':[]}
        save(out/'quality_report.json',report);return report,out
    def readiness(refs,**kw):
        meta=read(Path(refs[0].extraction)/'metadata.json');calls.append(('readiness',meta['product_id']))
        caps={key:{'status':status,'allow_preparation':status!='blocked','allow_scientific_execution':status=='ready'} for key,status in [('sky_visualization','ready'),('source_detection','conditional'),('temporal_comparison','blocked')]}
        report={**meta,'overall_processing_status':'completed','errors':[],'capabilities':caps}
        return report,save(tmp_path/'data/readiness'/f"{meta['product_id']}-{len(calls)}.json",report)
    def packages(path,**kw):
        r=read(path);pid=r['product_id'];calls.append(('packages',pid));folder=tmp_path/'data/algorithm_inputs'/f'{pid}-{len(calls)}';packages={}
        for key,decision in r['capabilities'].items():
            if decision['allow_preparation']:
                out=folder/key;save(out/'metadata.json',{'product_id':pid,'request_id':r['request_id'],'decision':decision});packages[key]={'path':str(out)}
        report={'status':'completed','packages':packages,'unavailable':{'temporal_comparison':r['capabilities']['temporal_comparison']}}
        return report,save(folder/'preparation_report.json',report)
    services.search=search;services.download_batch=download;services.extract=extract;services.validate_extraction=technical;services.evaluate_quality=quality;services.evaluate_readiness=readiness;services.prepare_packages=packages
    services.load_package=lambda path:SimpleNamespace(metadata=read(Path(path)/'metadata.json'))
    return services,calls,control

def start(tmp_path,mocked,ids=None):
    return run_pipeline(ids or ['p1'],value={'ra':10.,'dec':20.},goal='sky_viewer',fov_deg=.1,root=tmp_path,services=mocked[0],limits=WorkflowLimits(max_products=3))

def test_one_call_all_interfaces(tmp_path,mocked):
    w,p=start(tmp_path,mocked)
    assert w['status']=='completed' and w['completion_summary']['completed']==1
    assert w==read(p)
    assert {c[0] for c in mocked[1]}=={'search','download','extract','technical','quality','readiness','packages'}
    product=w['products']['p1'];assert len(product['stages'])==6
    assert product['readiness_capabilities']['source_detection']['allow_scientific_execution'] is False
    assert product['readiness_capabilities']['temporal_comparison']['status']=='blocked'
    assert all(stage['start_time'] and stage['end_time'] and stage['output_references'] for stage in product['stages'].values())

def test_three_products_independent_failure(tmp_path,mocked):
    mocked[2]['fail_product']='p2'
    w,p=start(tmp_path,mocked,['p1','p2','p3'])
    assert w['status']=='partial' and w['completion_summary']['completed']==2
    assert w['products']['p2']['stages']['technical_validation']['status']=='failed'
    assert w['products']['p2']['stages']['analysis_readiness']['status']=='skipped'
    assert w['products']['p3']['status']=='completed'
    assert w['group_temporal_readiness']=='not_evaluated'
    mocked[2]['fail_product']=None
    resumed,_=run_pipeline(resume=p,root=tmp_path,services=mocked[0])
    assert resumed['status']=='completed'
    assert sum(c[0]=='download' for c in mocked[1])==3

def test_interrupted_resume_no_redownload(tmp_path,mocked):
    mocked[2]['interrupt']='p2'
    with pytest.raises(KeyboardInterrupt):start(tmp_path,mocked,['p1','p2','p3'])
    path=next((tmp_path/'data/manifests').glob('workflow-*.json'))
    assert read(path)['products']['p2']['stages']['fits_extraction']['status']=='running'
    mocked[2]['interrupt']=None
    w,_=run_pipeline(resume=path,root=tmp_path,services=mocked[0])
    assert w['status']=='completed' and sum(c[0]=='download' for c in mocked[1])==3

def test_corrupt_download_not_reused(tmp_path,mocked):
    w,p=start(tmp_path,mocked)
    stage=w['products']['p1']['stages']['data_download'];Path(stage['result']['file']).write_bytes(b'CORRUPTED')
    w,_=run_pipeline(resume=p,root=tmp_path,services=mocked[0])
    assert w['status']=='completed' and sum(c[0]=='download' for c in mocked[1])==2

def test_request_mismatch_refused(tmp_path,mocked):
    w,p=start(tmp_path,mocked)
    record=w['products']['p1']['stages']['data_download']['result'];m=read(record['manifest']);m['request_id']='another';write(record['manifest'],m)
    product={'product_id':'p1','access_url':'https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/1.fits'}
    with pytest.raises(ValueError):checked_download(record['manifest'],w['stages']['user_input']['result']['request'],product,mocked[0])

def test_explicit_selection_required(tmp_path,mocked):
    for ids in ([],['p1','p1'],['p'+str(i) for i in range(386)]):
        with pytest.raises(ValueError):run_pipeline(ids,value={'ra':1,'dec':2},services=mocked[0],root=tmp_path)
    assert not mocked[1]

def test_resume_cannot_change_request_selection(tmp_path,mocked):
    _,p=start(tmp_path,mocked)
    with pytest.raises(ValueError):run_pipeline(['p2'],resume=p,root=tmp_path,services=mocked[0])

def test_cached_search_another_request(tmp_path,mocked):
    w,p=start(tmp_path,mocked);cached=w['stages']['archive_search']['result']['folder']
    result,_=run_pipeline(['p1'],value={'ra':10.,'dec':20.},fov_deg=.1,cached_search=cached,root=tmp_path,services=mocked[0])
    assert result['status']=='failed' and result['stages']['archive_search']['status']=='failed'
    assert sum(c[0]=='download' for c in mocked[1])==1

def test_workflow_download_budget(tmp_path,mocked):
    size=len(b'SYNTHETIC-TRANSPORT-FIXTURE')
    w,p=run_pipeline(['p1','p2','p3'],value={'ra':10.,'dec':20.},fov_deg=.1,root=tmp_path,services=mocked[0],limits=WorkflowLimits(max_products=3,max_network_bytes=size,max_file_bytes=size))
    assert w['status']=='partial' and w['completion_summary']['completed']==1
    assert sum(c[0]=='download' for c in mocked[1])==1
    assert w['network_budget_used']==size

def test_workflow_time_limit(tmp_path,mocked,monkeypatch):
    import orchestrator.runner as runner
    ticks=iter([0,2,3,4])
    monkeypatch.setattr(runner,'time',SimpleNamespace(monotonic=lambda:next(ticks)))
    w,p=run_pipeline(['p1'],value={'ra':10.,'dec':20.},root=tmp_path,services=mocked[0],limits=WorkflowLimits(max_seconds=1))
    assert w['status']=='failed' and not mocked[1]

def test_resume_cannot_change_request_file(tmp_path,mocked):
    w,p=start(tmp_path,mocked)
    with pytest.raises(ValueError):run_pipeline(resume=p,request_file=tmp_path/'another-request.json',root=tmp_path,services=mocked[0])

def test_reused_download_observation_identity(tmp_path,mocked):
    w,p=start(tmp_path,mocked)
    output=w['products']['p1']['stages']['data_download']['result']
    product={'product_id':'p1','observation_id':'another-exposure','access_url':'https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/1.fits'}
    with pytest.raises(ValueError,match='observation_id'):checked_download(output['manifest'],w['stages']['user_input']['result']['request'],product,mocked[0])
