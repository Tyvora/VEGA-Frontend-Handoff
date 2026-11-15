"""Bounded SIA2 metadata transport and VOTable decoding; no product fetching."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
import io, math, time
import requests
import numpy as np
from astropy.io.votable import parse

ENDPOINT='https://irsa.ipac.caltech.edu/SIA'
COLLECTIONS={'spherex_dr1':('DR1','wide'),'spherex_dr1_deep':('DR1','deep'),'spherex_qr3':('QR3','wide'),'spherex_qr3_deep':('QR3','deep')}
@dataclass(frozen=True)
class SIASettings:
    maxrec: int = 10000
    timeout: float = 45
    max_bytes: int = 32*1024*1024
    retries: int = 1
    def __post_init__(self):
        if self.maxrec<1 or self.timeout<=0 or self.max_bytes<1 or not 0<=self.retries<=3: raise ValueError('Invalid SIA settings')

def parameters(request: dict, collection: str, settings: SIASettings) -> dict:
    if collection not in COLLECTIONS: raise ValueError('Unknown collection')
    ra,dec,radius=request['ra_deg'],request['dec_deg'],request['fov_deg']/2
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in (ra,dec,radius)) or not 0<=ra<360 or not -90<=dec<=90 or not 0<radius<=.5 or request.get('coordinate_frame')!='icrs': raise ValueError('Invalid accepted geometry')
    return {'COLLECTION':collection,'POS':f'CIRCLE {ra:.12g} {dec:.12g} {radius:.12g}','DPTYPE':'image','CALIB':2,'FORMAT':'image/fits','MAXREC':settings.maxrec}

def decode(raw: bytes) -> tuple[list[dict],str,dict]:
    doc=parse(io.BytesIO(raw))
    infos=[i for resource in doc.resources for i in resource.infos if i.name=='QUERY_STATUS']
    if not infos or any(i.value=='ERROR' for i in infos): raise ValueError('Missing/failed QUERY_STATUS: '+str([i.content for i in infos]))
    status=infos[-1].value
    if status not in ('OK','OVERFLOW'): raise ValueError('Unrecognized QUERY_STATUS')
    table=doc.get_first_table().to_table(use_names_over_ids=True)
    rows=[]
    for row in table:
        rows.append({key: None if np.ma.is_masked(row[key]) else (row[key].item() if isinstance(row[key],np.generic) else row[key]) for key in table.colnames})
    return rows,status,{key:str(table[key].unit) if table[key].unit else None for key in table.colnames}

class SIAClient:
    def __init__(self, settings=SIASettings()): self.settings=settings
    def query(self, params: dict):
        for attempt in range(self.settings.retries+1):
            try:
                start=time.monotonic(); chunks=[]; size=0
                with requests.get(ENDPOINT,params=params,timeout=(10,self.settings.timeout),stream=True) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(65536):
                        size+=len(chunk)
                        if size>self.settings.max_bytes: raise ValueError('Response byte limit exceeded')
                        if time.monotonic()-start>self.settings.timeout: raise TimeoutError('Response time limit exceeded')
                        chunks.append(chunk)
                return decode(b''.join(chunks))
            except (requests.ConnectionError,requests.Timeout,TimeoutError):
                if attempt==self.settings.retries: raise
                time.sleep(.5*2**attempt)


def map_product(row: dict, collection: str) -> dict:
    release,survey=COLLECTIONS[collection]
    band=row.get('energy_bandpassname'); url=row.get('access_url'); identity=row.get('obs_publisher_did')
    eligible=bool(identity and isinstance(url,str) and urlparse(url).scheme=='https' and urlparse(url).hostname=='irsa.ipac.caltech.edu' and row.get('obs_collection')==collection and row.get('calib_level')==2 and row.get('dataproduct_type')=='image' and row.get('access_format')=='image/fits')
    return {'product_id':identity,'observation_id':row.get('obs_id'),'collection':collection,'collections':[collection],'data_release':release,'survey_type':survey,'detector':band[-2:] if band in [f'SPHEREx-D{i}' for i in range(1,7)] else None,'data_type':row.get('dataproduct_type'),'calibration_level':row.get('calib_level'),'access_url':url,'access_format':row.get('access_format'),'downloadable':eligible,'observation_start':row.get('t_min'),'observation_end':row.get('t_max'),'time_unit':'d (MJD)','time_scale':None,'footprint':row.get('s_region'),'coordinate_frame':'icrs','coordinate_unit':'deg','wavelength_min':row.get('em_min'),'wavelength_max':row.get('em_max'),'wavelength_unit':'m','processing_version':row.get('provenance_version'),'coverage_status':'intersects; full coverage and valid pixels unverified','source_service':ENDPOINT,'raw':row}

def sia_search(request: dict, acceptance: dict, client=None, settings=SIASettings(), collections=None):
    if acceptance.get('status')!='accepted' or acceptance.get('request_id')!=request.get('request_id') or acceptance.get('errors')!=[]: raise ValueError('Matching accepted report required')
    names=list(COLLECTIONS) if collections is None else list(collections)
    if not names or len(names)!=len(set(names)) or any(n not in COLLECTIONS for n in names): raise ValueError('Invalid collections')
    report={'request_id':request['request_id'],'service_used':'SIA2','query_start':datetime.now(timezone.utc).isoformat(),'collections_queried':names,'search_radius_deg':request['fov_deg']/2,'region_shape':'circle','queries':[],'warnings':[],'errors':[]}
    products=[]; raw=[]; seen={}; complete=True; successes=0
    client=client or SIAClient(settings)
    for name in names:
        params=parameters(request,name,settings); entry={'collection':name,'parameters':params,'endpoint':ENDPOINT}
        try:
            rows,status,units=client.query(params)
            if status not in ('OK','OVERFLOW'): raise ValueError('Invalid service status')
            successes+=1; raw.extend(rows)
            limited=status=='OVERFLOW' or len(rows)>=settings.maxrec
            complete &= not limited
            entry.update(number_of_results=len(rows),query_status=status,overflow=limited,units=units)
            for row in rows:
                if row.get('obs_collection')!=name or row.get('calib_level')!=2 or row.get('dataproduct_type')!='image':
                    complete=False; report['warnings'].append('Metadata filter mismatch in '+name); continue
                product=map_product(row,name)
                # Publisher ID alone can span processing versions. Preserve access variants.
                key=(product['product_id'],product['access_url'],product['processing_version'])
                if not product['product_id']: key=(*key,len(products))
                if key not in seen:
                    seen[key]=len(products); products.append(product)
                else:
                    previous=products[seen[key]]
                    if name not in previous['collections']: previous['collections'].append(name)
        except Exception as exc:
            complete=False; entry['error']=str(exc); report['errors'].append(name+': '+str(exc))
        report['queries'].append(entry)
    report.update(query_end=datetime.now(timezone.utc).isoformat(),number_of_results=len(raw),number_of_unique_products=len(products),completeness_status='complete' if complete else 'partial',overflow_detection=any(q.get('overflow',False) for q in report['queries']),status=('completed' if products else 'no_results') if complete else ('partial' if successes else 'failed'))
    if not complete: report['warnings'].append('No SIA pagination assumed; rerun with a larger bounded limit or use verified partitioning. No automatic partitioning implemented.')
    return {'schema_version':'1.0','products':products,'raw_rows':raw},report

