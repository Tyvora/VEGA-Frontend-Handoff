"""Evidence adapters for the existing extraction, technical and quality formats."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from datetime import datetime,timezone
from typing import Any
import hashlib,json,uuid,zipfile
import numpy as np
from .policy import VERSION,CAPABILITIES,Policy,assess,decision
ROOT=Path(__file__).resolve().parent.parent
SUPPORTED_QUALITY_POLICY='vega-dr1-qr3-conservative-1.0'
@dataclass(frozen=True)
class InputReferences:
    extraction: str|Path
    technical: str|Path
    quality: str|Path
class EvidenceError(ValueError):
    def __init__(self,code,message):super().__init__(message);self.code=code

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def read_json(path):
    try:
        with Path(path).open(encoding='utf-8') as stream:return json.load(stream)
    except FileNotFoundError as exc:raise EvidenceError('REPORT_MISSING',str(path)) from exc
    except (json.JSONDecodeError,UnicodeError) as exc:raise EvidenceError('REPORT_MALFORMED_JSON',str(path)) from exc

def require(ok,code,message):
    if not ok:raise EvidenceError(code,message)

def distribution(mask,grid_size):
    rows=np.array_split(mask,min(grid_size,mask.shape[0]),axis=0)
    counts=[int(cell.sum()) for row in rows for cell in np.array_split(row,min(grid_size,mask.shape[1]),axis=1)]
    return {'cell_counts':counts,'occupied_fraction':sum(v>0 for v in counts)/len(counts),'grid_shape':[len(rows),min(grid_size,mask.shape[1])],'definition':'Nonempty cells of an equal-index-space grid; not an estimator adequacy proof'}

def load_evidence(ref:InputReferences,policy:Policy)->dict:
    e,t,q=Path(ref.extraction).resolve(),Path(ref.technical).resolve(),Path(ref.quality).resolve()
    meta=read_json(e/'metadata.json');extraction=read_json(e/'report.json');technical=read_json(t);quality=read_json(q/'quality_report.json');metrics=read_json(q/'quality_metrics.json')
    require(extraction.get('status') in ('completed','partial'),'EXTRACTION_FAILED','Extraction failed')
    require(technical.get('overall_technical_status') in ('passed','passed_with_warnings') and not technical.get('errors') and technical.get('eligible_for_scientific_quality_validation') is True,'TECHNICAL_FAILED','Technical gate not satisfied')
    require(quality.get('quality_status') in ('passed','passed_with_warnings') and not quality.get('errors') and quality.get('ready_for_analysis_readiness') is True,'QUALITY_FAILED','Quality gate not satisfied')
    require(quality.get('quality_policy_version')==SUPPORTED_QUALITY_POLICY,'QUALITY_POLICY_UNSUPPORTED','Unknown quality policy')
    for path,expected in [(technical.get('extraction_reference'),e),(quality.get('extraction_reference'),e),(quality.get('technical_validation_reference'),t)]:
        require(isinstance(path,str) and Path(path).resolve()==expected,'REFERENCE_MISMATCH','Input references disagree')
    for key in ('request_id','product_id','observation_id'):
        values=[meta.get(key),technical.get(key),quality.get(key)]
        if key!='observation_id':require(all(isinstance(v,str) and v for v in values),'IDENTITY_UNPROVEN','Missing '+key)
        require(len(set(v for v in values if v is not None))<=1,'IDENTITY_MISMATCH',key)
    require(extraction.get('product_id')==meta.get('product_id'),'IDENTITY_MISMATCH','Extraction product mismatch')
    hashes=technical.get('provenance_checks',{}).get('extraction_file_sha256',{})
    for name in ('arrays.npz','tables.fits','metadata.json','report.json'):
        require((e/name).is_file(),'EXTRACTION_FILE_MISSING',name)
        require(digest(e/name)==hashes.get(name),'EXTRACTION_HASH_MISMATCH',name)
    with zipfile.ZipFile(e/'arrays.npz') as z:require(sum(i.file_size for i in z.infolist())<=512*1024*1024,'RESOURCE_LIMIT','Expanded arrays exceed readiness budget')
    with zipfile.ZipFile(q/'masks.npz') as z:require(sum(i.file_size for i in z.infolist())<=128*1024*1024,'RESOURCE_LIMIT','Expanded masks exceed readiness budget')
    with np.load(e/'arrays.npz',allow_pickle=False) as data:
        image=data['IMAGE'];variance=data['VARIANCE'] if 'VARIANCE' in data else None
    with np.load(q/'masks.npz',allow_pickle=False) as data:
        a=data['analysis_mask'];b=data['background_mask'];ar=data['analysis_exclusion_reasons'];br=data['background_exclusion_reasons']
    require(image.ndim==2 and image.size>0,'IMAGE_MISSING','No nonempty 2D image')
    require(a.dtype==bool and b.dtype==bool and a.shape==b.shape==image.shape and ar.shape==br.shape==image.shape,'MASK_INVALID','Mask shape/type mismatch')
    require(np.array_equal(a,ar==0) and np.array_equal(b,br==0) and not (b&~a).any(),'MASK_INVALID','Mask/reason inconsistency')
    require(list(a.shape)==quality.get('mask_shape') and quality.get('mask_dtype')=='bool','MASK_INVALID','Quality report mask description mismatch')
    total=int(a.size);ac=int(a.sum());bc=int(b.sum())
    facts={'total_pixels':total,'analysis_usable_pixels':ac,'background_candidate_pixels':bc,'analysis_usable_fraction':ac/total,'background_candidate_fraction':bc/total}
    for key,value in facts.items():
        require(metrics.get(key)==value and quality.get('pixel_counts',{}).get(key)==value,'MASK_METRICS_MISMATCH',key)
    require(np.isfinite(image[a]).all(),'MASK_INVALID','Analysis mask includes nonfinite image')
    if variance is not None:require(variance.shape==a.shape and np.isfinite(variance[a]).all() and (variance[a]>0).all(),'MASK_INVALID','Analysis variance inconsistent')
    caps=technical.get('capabilities',{});extensions={x['name']:x for x in meta.get('extensions',[])}
    noise=metrics.get('sqrt_variance_statistics',{})
    observation=meta.get('observation_metadata',{});raw=meta.get('download_entry',{}).get('source_metadata',{}).get('raw',{})
    time_value=observation.get('MJD-BEG')
    if not isinstance(time_value,(float,int)) or not np.isfinite(time_value):time_value=None
    refs={'extraction':str(e),'technical_validation':str(t),'quality_validation':str(q),'quality_policy_version':quality['quality_policy_version']}
    files=[e/'arrays.npz',e/'tables.fits',e/'metadata.json',e/'report.json',t,q/'masks.npz',q/'quality_report.json',q/'quality_metrics.json']
    bg=distribution(b,policy.grid_size);analysis=distribution(a,policy.grid_size)
    return {'request_id':meta['request_id'],'product_id':meta['product_id'],'observation_id':meta.get('observation_id'),'observation_time':time_value,'time_reference':observation.get('TIMESYS'),'bandpass':raw.get('energy_bandpassname'),'image':True,'variance':variance is not None,'units':technical.get('units_checks',{}).get('IMAGE',{}).get('valid') is True and bool(extensions.get('IMAGE',{}).get('unit')),'wcs':caps.get('spatial_wcs_available') is True and technical.get('wcs_checks',{}).get('valid') is True,'epsf':caps.get('epsf_available') is True and 'EPSF' in extensions,'spectral_table':caps.get('spectral_table_valid') is True,'spectral_maps':caps.get('spectral_maps_available') is True,'noise':noise.get('count',0)>0 and isinstance(noise.get('median'),(float,int)) and bool(np.isfinite(noise['median'])),'analysis_pixels':ac,'analysis_fraction':ac/total,'background_pixels':bc,'background_fraction':bc/total,'background_distribution':bg,'background_occupied_fraction':bg['occupied_fraction'],'analysis_distribution':analysis,'analysis_occupied_fraction':analysis['occupied_fraction'],'references':refs,'input_sha256':{str(p):digest(p) for p in files},'calibration_evidence':{'pixel_solid_angle_map':'not supplied','photometric_method_calibration':'not supplied','science_CWAVE_CBAND':'not supplied'},'warnings':['Quality outputs have no producer-signed hash baseline; policy/version, reasons, counts, identity and references checked; current hashes recorded, not independent proof of mask authorship']+quality.get('warnings',[])}

def evaluate_readiness(inputs:list[InputReferences],*,policy:Policy=Policy(),output_dir:str|Path|None=None)->tuple[dict,Path]:
    report={'schema_version':'1.0','readiness_policy_version':VERSION,'request_id':None,'observation_id':None,'product_id':None,'evaluation_timestamp':datetime.now(timezone.utc).isoformat(),'policy_settings':asdict(policy),'capabilities':{},'evidence':[],'warnings':[],'errors':[],'overall_processing_status':'failed'}
    try:
        require(bool(inputs),'INPUTS_MISSING','No input references')
        records=[load_evidence(ref,policy) for ref in inputs]
        # Duplicate prepared products do not create independent exposures.
        require(len({r['product_id'] for r in records})==len(records),'DUPLICATE_PREPARED_PRODUCT','Repeated product reference')
        for key in ('request_id','observation_id','product_id'):report[key]=records[0][key]
        for key,value in records[0]['references'].items():report[key+'_reference' if not key.endswith('version') else key]=value
        report['evidence']=records;report['capabilities']=assess(records,policy)
        report['warnings']=[w for r in records for w in r['warnings']]
        for r in records:
            for path,sha in r['input_sha256'].items():require(digest(path)==sha,'INPUT_CHANGED_DURING_EVALUATION',path)
        report['overall_processing_status']='completed'
    except Exception as exc:
        code=exc.code if isinstance(exc,EvidenceError) else 'INPUT_UNREADABLE'
        report['errors'].append({'reason_code':code,'message':str(exc)})
        report['capabilities']={name:decision('blocked',[code],{},['Verified consistent input evidence'],['Correct input reports and rerun readiness']) for name in CAPABILITIES}
    serialized=json.dumps(report,indent=2,allow_nan=False)
    folder=(Path(output_dir) if output_dir else ROOT/'data'/'readiness')/str(uuid.uuid4());folder.mkdir(parents=True)
    path=folder/'readiness_report.json'
    with path.open('x',encoding='utf-8') as stream:stream.write(serialized)
    require(json.loads(path.read_text())==report,'REPORT_READBACK_FAILED','Readiness report changed on readback')
    return report,path

