"""One-call, checkpointed coordination of the nine existing public stage APIs."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Any
import time,uuid
from .services import Services,Limits,SIASettings,InputReferences
from .state import now,sha,read,write,snapshot,run_stage,skipped,StageFailure
ROOT=Path(__file__).resolve().parent.parent
PRODUCT_STAGES=('data_download','fits_extraction','technical_validation','scientific_quality_validation','analysis_readiness','algorithm_inputs')
@dataclass(frozen=True)
class WorkflowLimits:
    max_products:int=1
    max_file_bytes:int=32*1024*1024
    max_network_bytes:int=64*1024*1024
    max_seconds:float=300
    read_timeout:float=60
    download_retries:int=0
    def __post_init__(self):
        if min(self.max_products,self.max_file_bytes,self.max_network_bytes,self.max_seconds,self.read_timeout)<=0 or not 0<=self.download_retries<=3:raise ValueError('Invalid workflow limits')

def checked_download(path,request,product,services):
    m=read(path)
    if m.get('request_id')!=request['request_id']:raise ValueError('Download belongs to another request')
    entries=[e for e in m.get('entries',[]) if e.get('product_id')==product['product_id'] and e.get('download_status')=='downloaded']
    if len(entries)!=1:raise ValueError('No unique completed download')
    e=entries[0];_,params=services.build_url(product,request,'cutout')
    for field in ('observation_id','collection'):
        if product.get(field) is not None and e.get(field)!=product[field]:raise ValueError('Downloaded product metadata mismatch: '+field)
    if e.get('request_id')!=request['request_id'] or e.get('source_url')!=product.get('access_url') or e.get('cutout_parameters')!=params or e.get('download_mode')!='cutout':raise ValueError('Download identity/geometry mismatch')
    file=Path(e['local_file_path'])
    if file.stat().st_size!=e['file_size'] or sha(file)!=e['sha256']:raise ValueError('Downloaded file integrity mismatch')
    return e

def imported_bundle(path,request,product,services):
    result=read(path)
    if result.get('status')!='completed' or not result.get('packages'):raise ValueError('Imported package run not complete')
    packages=[services.load_package(v['path']) for v in result['packages'].values()]
    refs=packages[0].metadata['references']
    for package in packages:
        if package.metadata['request_id']!=request['request_id'] or package.metadata['product_id']!=product['product_id'] or package.metadata['references']!=refs:raise ValueError('Imported package request/product mismatch')
    for package in packages:
        for field in ('observation_id','collection'):
            if product.get(field) is not None and package.metadata.get(field)!=product[field]:raise ValueError('Imported package metadata mismatch: '+field)
    metadata=read(Path(refs['extraction'])/'metadata.json')
    checked_download(metadata['download_manifest'],request,product,services)
    return {'download':metadata['download_manifest'],'extraction':refs['extraction'],'technical':refs['technical_validation'],'quality':refs['quality_validation'],'readiness':refs['readiness_report'],'packages':str(Path(path).resolve())}

def run_pipeline(selected_product_ids:list[str]|None=None,*,method:str='coordinates',value:Any=None,goal:str='sky_viewer',fov_deg:float|None=None,request_file:str|Path|None=None,cached_search:str|Path|None=None,reuse_packages:dict[str,str]|None=None,resume:str|Path|None=None,limits:WorkflowLimits|None=None,services:Services|None=None,root:Path=ROOT):
    services=services or Services();root=Path(root).resolve()
    for directory in ('manifests','requests','validation','search_results'):(root/'data'/directory).mkdir(parents=True,exist_ok=True)
    if resume:
        manifest=Path(resume).resolve();workflow=read(manifest)
        if workflow.get('workflow_schema_version')!='1.0' or Path(workflow['pipeline_root'])!=root:raise ValueError('Incompatible workflow manifest/root')
        if selected_product_ids is not None and selected_product_ids!=workflow['selected_product_ids']:raise ValueError('Cannot change selection during resume')
        if limits is not None and asdict(limits)!=workflow['limits']:raise ValueError('Resume limits must match original run')
        limits=WorkflowLimits(**workflow['limits']);selected_product_ids=workflow['selected_product_ids'];inv=workflow['invocation']
        for supplied,key in ((request_file,'request_file'),(cached_search,'cached_search')):
            if supplied is not None and str(Path(supplied).resolve())!=inv[key]:raise ValueError('Cannot change source references during resume')
        if value is not None and value!=inv['value']:raise ValueError('Cannot change user input during resume')
        if fov_deg is not None and fov_deg!=inv['fov_deg']:raise ValueError('Cannot change FOV during resume')
        if reuse_packages is not None and reuse_packages!=inv['reuse_packages']:raise ValueError('Cannot change imported bundles during resume')
    else:
        limits=limits or WorkflowLimits()
        if not selected_product_ids or len(selected_product_ids)>limits.max_products or len(set(selected_product_ids))!=len(selected_product_ids):raise ValueError('Explicit unique bounded product selection required')
        inv={'method':method,'value':value,'goal':goal,'fov_deg':fov_deg,'request_file':str(Path(request_file).resolve()) if request_file else None,'cached_search':str(Path(cached_search).resolve()) if cached_search else None,'reuse_packages':reuse_packages or {}}
        runid=str(uuid.uuid4());manifest=root/'data'/'manifests'/('workflow-'+runid+'.json')
        workflow={'workflow_schema_version':'1.0','run_id':runid,'request_id':None,'pipeline_root':str(root),'status':'pending','created_at':now(),'selected_product_ids':selected_product_ids,'limits':asdict(limits),'invocation':inv,'stages':{},'products':{pid:{'status':'pending','stages':{},'package_references':[]} for pid in selected_product_ids},'network_budget_used':0,'network_bytes_recorded':0,'errors':[],'warnings':['Readiness remains per prepared product; group temporal readiness is not inferred from product count'],'group_temporal_readiness':'not_evaluated'}
        def pending():return {'status':'pending','start_time':None,'end_time':None,'input_references':[],'output_references':[],'errors':[],'warnings':[]}
        workflow['stages']={name:pending() for name in ('user_input','request_validation','archive_search','observation_selection')}
        for product_record in workflow['products'].values():product_record['stages']={name:pending() for name in PRODUCT_STAGES}
        with manifest.open('x',encoding='utf-8') as f:
            import json
            json.dump(workflow,f,indent=2)
    start=time.monotonic();deadline=start+limits.max_seconds
    if workflow.get('errors'):
        workflow.setdefault('error_history',[]).extend(workflow['errors']);workflow['errors']=[]
    workflow['status']='running';workflow['last_started_at']=now();write(manifest,workflow)
    def stage(stages,name,inputs,op):
        def guarded():
            if time.monotonic()>deadline:raise TimeoutError('Workflow time budget exhausted before '+name)
            return op()
        return run_stage(workflow,manifest,stages,name,inputs,guarded)
    def inputs(request,paths=(),**extra):return {'request':request,'files':snapshot(paths),**extra}
    stages=workflow['stages']
    try:
        def user_input():
            request=read(inv['request_file']) if inv['request_file'] else services.create_request(inv['method'],inv['value'],inv['goal'],fov_deg=inv['fov_deg'])
            target=root/'data'/'requests'/(request['request_id']+'.json')
            if target.exists():
                if read(target)!=request:raise ValueError('Request ID collision with different content')
            else:target=services.save_request(request,root/'data'/'requests')
            return {'request':request,'path':str(target)},[target],'completed',['Supplied normalized request reused'] if inv['request_file'] else []
        u=stage(stages,'user_input',{'invocation':inv,'request_source':snapshot([inv['request_file']]) if inv['request_file'] else {}},user_input)
        request=u['request'];workflow['request_id']=request['request_id']
        def validation():
            result,accepted=services.validate_request(request);path=services.save_report(result,root/'data'/'validation')
            if accepted is None:raise StageFailure('Request rejected: '+str(result['errors']),[path],{'report':str(path)})
            return {'report':str(path)},[path],'completed',result.get('warnings',[])
        v=stage(stages,'request_validation',inputs(request,[u['path']]),validation);acceptance=read(v['report'])
        def archive():
            if inv['cached_search']:
                folder=Path(inv['cached_search']);catalog=services.load_catalog(folder/'catalog.json');report=read(folder/'report.json')
                if report.get('request_id')!=request['request_id'] or report.get('status') not in ('completed','partial','no_results'):raise ValueError('Cached search request/status mismatch')
                if report.get('service_used')!='SIA2' or not report.get('queries'):raise ValueError('Only geometry-documented SIA2 cache reuse supported')
                for query in report['queries']:
                    shape,ra,dec,radius=query['parameters']['POS'].split()
                    if shape.upper()!='CIRCLE' or any(abs(a-b)>1e-9 for a,b in zip((float(ra),float(dec),float(radius)),(request['ra_deg'],request['dec_deg'],request['fov_deg']/2))):raise ValueError('Cached search geometry mismatch')
            else:
                catalog,report=services.search(request,acceptance,settings=SIASettings(timeout=min(30,limits.max_seconds),retries=0))
                folder=services.save_results(catalog,report,root/'data'/'search_results')
                if report.get('status')=='failed':raise StageFailure('Archive search failed: '+str(report.get('errors')),[folder/'catalog.json',folder/'report.json'],{'folder':str(folder)})
            return {'folder':str(folder),'reused_from_existing':bool(inv['cached_search'])},[folder/'catalog.json',folder/'report.json'],'partial' if report['status']=='partial' else 'completed',report.get('warnings',[])
        a=stage(stages,'archive_search',inputs(request,[v['report']]+([Path(inv['cached_search'])/'catalog.json',Path(inv['cached_search'])/'report.json'] if inv['cached_search'] else [])),archive)
        catalog_path=Path(a['folder'])/'catalog.json';catalog=services.load_catalog(catalog_path);search_report=read(Path(a['folder'])/'report.json')
        workflow['archive_search_status']=search_report['status']
        if search_report['status']=='partial' and 'Selected products come from a partial archive catalog' not in workflow['warnings']:workflow['warnings'].append('Selected products come from a partial archive catalog')
        def selection():
            products=[]
            for pid in selected_product_ids:
                matches=[p for p in catalog['products'] if p.get('product_id')==pid]
                if len(matches)!=1 or matches[0].get('downloadable') is not True:raise ValueError('Selection missing, ambiguous or not downloadable: '+pid)
                products.append(matches[0])
            path=root/'data'/'manifests'/('selection-'+workflow['run_id']+'.json');write(path,{'request_id':request['request_id'],'products':products})
            return {'path':str(path)},[path],'completed',[]
        s=stage(stages,'observation_selection',inputs(request,[catalog_path],selected=selected_product_ids),selection)
        products=read(s['path'])['products']
    except Exception as exc:
        workflow['errors'].append({'scope':'request','message':str(exc)});workflow['status']='failed'
        skipped(stages,('user_input','request_validation','archive_search','observation_selection'),'Upstream stage failed')
        for record in workflow['products'].values():record['status']='skipped';skipped(record['stages'],PRODUCT_STAGES,'Request/selection failed')
        workflow['ended_at']=now();write(manifest,workflow);return workflow,manifest
    for product in products:
        pid=product['product_id'];record=workflow['products'][pid];ps=record['stages']
        if record.get('errors'):
            record.setdefault('error_history',[]).extend(record['errors']);record['errors']=[]
        record.update(status='running',observation_id=product.get('observation_id'),observation_start=product.get('observation_start'),detector=product.get('detector'));write(manifest,workflow)
        try:
            bundle=imported_bundle(inv['reuse_packages'][pid],request,product,services) if pid in inv['reuse_packages'] else {}
            def download():
                candidates=[Path(bundle['download'])] if bundle else list((root/'data'/'manifests').glob('*.json'))
                for candidate in candidates:
                    try:
                        entry=checked_download(candidate,request,product,services)
                        return {'manifest':str(candidate),'file':entry['local_file_path'],'reused_from_existing':True},[candidate,entry['local_file_path']],'completed',['Verified prior download reused; zero network bytes']
                    except (OSError,ValueError,KeyError,TypeError):continue
                remaining=limits.max_network_bytes-workflow['network_budget_used']
                if remaining<=0:raise ValueError('Network download budget exhausted')
                reservation=min(remaining,limits.max_file_bytes*(limits.download_retries+1))
                workflow['network_budget_used']+=reservation;write(manifest,workflow)
                entries,path=services.download_batch(catalog,search_report,request,acceptance,[pid],limits=Limits(max_file_bytes=limits.max_file_bytes,max_total_bytes=reservation,max_products=1,read_timeout=limits.read_timeout,retries=limits.download_retries),root=root,cancelled=lambda:time.monotonic()>deadline)
                downloaded=read(path);actual=downloaded['network_bytes'];workflow['network_budget_used']+=actual-reservation;workflow['network_bytes_recorded']+=actual;write(manifest,workflow)
                if entries[0].get('download_status')!='downloaded':raise StageFailure('Download failed: '+str(entries[0].get('error_details')),[path],{'manifest':str(path)})
                entry=checked_download(path,request,product,services)
                return {'manifest':str(path),'file':entry['local_file_path']},[path,entry['local_file_path']],'completed',entries[0].get('warnings',[])
            d=stage(ps,'data_download',inputs(request,[catalog_path,v['report']],product=product),download)
            def extraction():
                if bundle:
                    folder=Path(bundle['extraction']);result=read(folder/'report.json');meta=read(folder/'metadata.json')
                    if meta['request_id']!=request['request_id'] or meta['product_id']!=pid or Path(meta['source_fits_path']).resolve()!=Path(d['file']).resolve():raise ValueError('Imported extraction identity mismatch')
                else:result,folder=services.extract(d['manifest'],pid,root=root)
                if result.get('status')=='failed':raise StageFailure('Extraction failed: '+str(result.get('errors')),[folder],{'folder':str(folder)})
                return {'folder':str(folder),'reused_from_existing':bool(bundle)},[folder],'partial' if result['status']=='partial' else 'completed',result.get('warnings',[])
            e=stage(ps,'fits_extraction',inputs(request,[d['manifest'],d['file']],product_id=pid),extraction)
            def technical():
                if bundle:path=Path(bundle['technical']);result=read(path)
                else:result,path=services.validate_extraction(e['folder'],output_dir=root/'data'/'validation')
                if result.get('errors') or result.get('overall_technical_status') not in ('passed','passed_with_warnings'):raise StageFailure('Technical validation failed: '+str(result.get('errors')),[path],{'report':str(path)})
                return {'report':str(path),'reused_from_existing':bool(bundle)},[path],'completed',result.get('warnings',[])
            t=stage(ps,'technical_validation',inputs(request,[e['folder']],product_id=pid),technical)
            def quality():
                if bundle:folder=Path(bundle['quality']);result=read(folder/'quality_report.json')
                else:result,folder=services.evaluate_quality(e['folder'],t['report'],output_dir=root/'data'/'quality')
                if result.get('errors') or result.get('quality_status') not in ('passed','passed_with_warnings'):raise StageFailure('Quality validation failed: '+str(result.get('errors')),[folder],{'folder':str(folder)})
                return {'folder':str(folder),'reused_from_existing':bool(bundle)},[folder],'completed',result.get('warnings',[])
            q=stage(ps,'scientific_quality_validation',inputs(request,[e['folder'],t['report']],product_id=pid),quality)
            def readiness():
                if bundle:path=Path(bundle['readiness']);result=read(path)
                else:result,path=services.evaluate_readiness([InputReferences(e['folder'],t['report'],q['folder'])],output_dir=root/'data'/'readiness')
                if result.get('overall_processing_status')!='completed' or result.get('errors'):raise StageFailure('Readiness evidence evaluation failed: '+str(result.get('errors')),[path],{'report':str(path)})
                return {'report':str(path),'capabilities':result['capabilities'],'reused_from_existing':bool(bundle)},[path],'completed',result.get('warnings',[])
            r=stage(ps,'analysis_readiness',inputs(request,[e['folder'],t['report'],q['folder']],product_id=pid),readiness)
            def packages():
                if bundle:path=Path(bundle['packages']);result=read(path)
                else:result,path=services.prepare_packages(r['report'],output_dir=root/'data'/'algorithm_inputs')
                if result.get('status')!='completed':raise ValueError('Package preparation did not complete')
                for entry in result['packages'].values():
                    package=services.load_package(entry['path'])
                    if package.metadata['product_id']!=pid or package.metadata['request_id']!=request['request_id']:raise ValueError('Package identity mismatch')
                return {'report':str(path),'packages':result['packages'],'unavailable':result['unavailable'],'reused_from_existing':bool(bundle)},[path]+[p['path'] for p in result['packages'].values()],'completed',[]
            p=stage(ps,'algorithm_inputs',inputs(request,[r['report']],product_id=pid),packages)
            # Public reader rechecks external references even on a resumed complete stage.
            for entry in p['packages'].values():services.load_package(entry['path'])
            record.update(status='completed',package_references=[x['path'] for x in p['packages'].values()],readiness_capabilities=r['capabilities'])
        except Exception as exc:
            record['status']='failed';record['package_references']=[];record.setdefault('errors',[]).append(str(exc));skipped(ps,PRODUCT_STAGES,'Product failed upstream; other products continue')
        write(manifest,workflow)
    count=sum(p['status']=='completed' for p in workflow['products'].values())
    workflow.update(status='completed' if count==len(products) else 'partial' if count else 'failed',ended_at=now(),completion_summary={'selected':len(products),'completed':count,'failed':sum(p['status']=='failed' for p in workflow['products'].values()),'network_bytes_recorded':workflow['network_bytes_recorded'],'network_budget_used':workflow['network_budget_used']})
    write(manifest,workflow);return workflow,manifest





