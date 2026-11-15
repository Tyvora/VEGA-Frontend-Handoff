"""Conservative IRSA TAP metadata search; no product downloads."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import math
import time
import uuid
import requests
import pyvo
from .catalog import normalize

ENDPOINT='https://irsa.ipac.caltech.edu/TAP'

class TimedSession(requests.Session):
    def request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', (10,30))
        return super().request(method,url,**kwargs)

@dataclass(frozen=True)
class Settings:
    maxrec: int = 1000
    retries: int = 1
    async_mode: bool = False
    job_timeout: float = 60

class TapClient:
    def __init__(self, async_mode: bool = False, job_timeout: float = 60):
        self.async_mode, self.job_timeout = async_mode, job_timeout
        self.service=pyvo.dal.TAPService(ENDPOINT,session=TimedSession())
    def query(self, query: str, maxrec: int):
        if not self.async_mode:
            result=self.service.run_sync(query,maxrec=maxrec)
        else:
            job=self.service.submit_job(query,maxrec=maxrec)
            try:
                job.run()
                job.wait(phases=['COMPLETED','ERROR','ABORTED'],timeout=self.job_timeout)
                if job.phase!='COMPLETED':
                    job.abort()
                    raise RuntimeError('Async job did not complete: '+job.phase)
                job.raise_if_error()
                result=job.fetch_result()
            finally:
                job.delete()
        return [{key: (None if str(row[key])=='--' else str(row[key])) for key in result.fieldnames} for row in result], result.query_status

def build_query(request: dict[str,Any]) -> str:
    ra,dec,radius=request['ra_deg'],request['dec_deg'],request['fov_deg']/2
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (ra,dec,radius)): raise ValueError('Nonfinite query geometry')
    return f"SELECT a.artifactid,a.uri,a.producttype,a.contenttype,p.productid,p.calibrationlevel,p.obsid,p.energy_bandpassname,p.time_bounds_lower,p.provenance_version,o.collection,o.observationid FROM spherex.artifact a JOIN spherex.plane p ON a.planeid=p.planeid JOIN spherex.observation o ON p.obsid=o.obsid WHERE 1=INTERSECTS(CIRCLE('ICRS',{ra:.12g},{dec:.12g},{radius:.12g}),p.poly)"

def search(request: dict[str,Any], acceptance: dict[str,Any], client=None, settings=Settings()):
    if acceptance.get('status')!='accepted' or acceptance.get('request_id')!=request.get('request_id') or acceptance.get('errors')!=[]: raise ValueError('Matching accepted validation report required')
    if settings.maxrec<1 or not 0<=settings.retries<=3: raise ValueError('Invalid operational settings')
    query=build_query(request)
    report={'request_id':request['request_id'],'status':'failed','query_timestamp':datetime.now(timezone.utc).isoformat(),'tap_endpoint':ENDPOINT,'query_parameters':{'radius_deg':request['fov_deg']/2,'maxrec':settings.maxrec},'adql':query,'number_of_results':0,'completeness':{'proven':False},'warnings':[],'errors':[],'data_releases':['DR1','QR3'],'query_strategy':'bounded INTERSECTS probe; release classification unverified'}
    raw=[]
    try:
        client=client or TapClient(settings.async_mode,settings.job_timeout)
        for attempt in range(settings.retries+1):
            try:
                raw,status=client.query(query,settings.maxrec)
                break
            except (requests.RequestException,pyvo.dal.DALServiceError):
                if attempt==settings.retries: raise
                time.sleep(.5*2**attempt)
        report['completeness']['tap_status']=status
        report['completeness']['overflow']=status=='OVERFLOW' or len(raw)>=settings.maxrec
        # Fail closed: metadata interpretation must be verified before publishing products.
        report['status']='partial' if raw else ('no_results' if status=='OK' else 'failed')
        report['warnings'].append('DR1/QR3, L2 MEF classification and full retrieval are not verified; raw rows are diagnostic only, not a download catalog.')
        report['number_of_results']=len(raw)
    except Exception as exc:
        report['errors'].append(str(exc))
    products, warnings = normalize(raw)
    report['warnings'].extend(warnings)
    report['catalog_product_count']=len(products)
    return {'products':products, 'raw_rows':raw},report

def save_results(catalog: dict, report: dict, directory: str | Path | None=None) -> Path:
    root=Path(directory) if directory else Path(__file__).resolve().parent.parent/'data'/'search_results'
    folder=root/str(uuid.uuid4())
    folder.mkdir()
    for name,value in [('catalog.json',catalog),('report.json',report)]:
        with (folder/name).open('x',encoding='utf-8') as stream: json.dump(value,stream,indent=2,allow_nan=False)
    return folder

