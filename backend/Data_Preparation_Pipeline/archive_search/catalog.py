"""Lossless metadata mapping and identity-based duplicate detection."""
from typing import Any
from urllib.parse import urljoin,urlparse

ROOT='https://irsa.ipac.caltech.edu/'

def normalize(rows: list[dict[str,Any]]) -> tuple[list[dict[str,Any]],list[str]]:
    products=[]; seen={}; warnings=[]
    for row in rows:
        identity=row.get('artifactid')
        if not identity:
            warnings.append('Row without artifactid retained only in raw rows')
            continue
        if identity in seen:
            if seen[identity]!=row: warnings.append('Conflicting metadata for artifactid '+str(identity))
            else: continue
        seen[identity]=row
        uri=row.get('uri')
        url=urljoin(ROOT,uri) if isinstance(uri,str) and uri else None
        if url and (urlparse(url).scheme!='https' or urlparse(url).hostname!='irsa.ipac.caltech.edu'): url=None
        band=row.get('energy_bandpassname')
        detector=band[-2:] if band in [f'SPHEREx-D{i}' for i in range(1,7)] else None
        products.append({'artifact_id':identity,'product_id':row.get('productid'),'observation_id':row.get('observationid'),'obsid':row.get('obsid'),'data_release':None,'survey_type':None,'detector':detector,'observation_time':row.get('time_bounds_lower'),'time_reference':'MJD; timescale unspecified' if row.get('time_bounds_lower') is not None else None,'bandpass':band,'footprint':row.get('poly'),'coverage_status':'unknown','processing_version':row.get('provenance_version'),'artifact_uri':uri,'access_url':url,'downloadable':False,'classification_status':'unverified_release_and_L2_MEF','source_tables':['spherex.artifact','spherex.plane','spherex.observation'],'raw':row})
    return products,warnings
