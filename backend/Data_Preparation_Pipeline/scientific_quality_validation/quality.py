from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,uuid
import numpy as np
from astropy.io import fits
from astropy import units as u
from .policy import POLICY_VERSION,REFERENCE,EXPECTED,CRITICAL,CAUTION,INFORMATIONAL,BACKGROUND
ROOT=Path(__file__).resolve().parent.parent

def digest(path:Path)->str:
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def summary(values:np.ndarray)->dict:
    a=np.asarray(values,dtype=np.float64)
    if not a.size:return {'count':0,'minimum':None,'median':None,'maximum':None,'percentiles_5_25_75_95':None}
    return {'count':int(a.size),'minimum':float(a.min()),'median':float(np.median(a)),'maximum':float(a.max()),'percentiles_5_25_75_95':np.percentile(a,[5,25,75,95]).tolist()}

def evaluate_pixels(image:np.ndarray,variance:np.ndarray,flags:np.ndarray,header:fits.Header,zodi:np.ndarray|None=None)->tuple[dict,dict,list]:
    if image.ndim!=2 or not image.size or variance.shape!=image.shape or flags.shape!=image.shape or flags.dtype.kind not in 'iu':raise ValueError('Invalid array structure')
    if flags.dtype.itemsize>8:raise ValueError('Unsupported FLAGS width')
    # Preserve bit patterns, including signed integer sign bits.
    bits=flags.view(np.dtype(flags.dtype.str.replace('i','u'))) if flags.dtype.kind=='i' else flags
    bits=bits.astype(np.uint64)
    critical=np.zeros(image.shape,bool);caution=critical.copy();source=critical.copy();unknown=critical.copy()
    definitions=[];warnings=[];flag_counts={};category_counts={k:0 for k in ['critical','warning','source_background_exclusion','informational','unknown']};unions={k:critical.copy() for k in category_counts}
    for bit in range(flags.dtype.itemsize*8):
        name=header.get(f'MSKN{bit:04d}');description=header.get(f'MSKD{bit:04d}')
        active=(bits & np.uint64(1<<bit))!=0
        verified=name is not None and EXPECTED.get(bit)==str(name).strip()
        if verified:
            category='critical' if name in CRITICAL else 'warning' if name in CAUTION else 'source_background_exclusion' if name in BACKGROUND else 'informational'
        else:category='unknown'
        count=int(active.sum());label=f'{bit}:{name or "UNDEFINED"}'
        if count:flag_counts[label]={'bit':bit,'name':name,'count':count,'fraction':count/image.size,'category':category}
        if name is not None:
            definitions.append({'bit':bit,'name':name,'description':description,'category':category,'matches_reference':verified})
            if not verified:warnings.append('Definition mismatch/unknown at bit '+str(bit))
        unions[category]|=active
    critical=unions['critical'];caution=unions['warning'];source=unions['source_background_exclusion'];unknown=unions['unknown']
    if not definitions:warnings.append('No flag definitions in header; active bits treated as unknown')
    if unknown.any():warnings.append('Unknown active flag bits excluded by VEGA policy')
    if caution.any():warnings.append('Caution flags retained in analysis, excluded from background candidates')
    image_invalid=~np.isfinite(image);variance_invalid=~np.isfinite(variance)|(variance<=0)
    reasons=image_invalid.astype(np.uint8) | (variance_invalid.astype(np.uint8)<<1) | (critical.astype(np.uint8)<<2) | (unknown.astype(np.uint8)<<3)
    analysis=reasons==0
    background_reasons=reasons | (source.astype(np.uint8)<<4) | (caution.astype(np.uint8)<<5)
    background=background_reasons==0
    total=image.size
    positive=np.isfinite(variance)&(variance>0)
    stats=summary(variance[analysis]);noise=summary(np.sqrt(variance[analysis].astype(np.float64)))
    metrics={'total_pixels':int(total),'analysis_usable_pixels':int(analysis.sum()),'analysis_usable_fraction':float(analysis.mean()),'background_candidate_pixels':int(background.sum()),'background_candidate_fraction':float(background.mean()),'flag_counts':flag_counts,'category_pixel_counts':{k:int(v.sum()) for k,v in unions.items()},'invalid_variance_count':int(variance_invalid.sum()),'invalid_variance_fraction':float(variance_invalid.mean()),'nonpositive_variance_count':int((np.isfinite(variance)&(variance<=0)).sum()),'nonpositive_variance_fraction':float((np.isfinite(variance)&(variance<=0)).mean()),'nonfinite':{name:{'nan':int(np.isnan(a).sum()),'inf':int(np.isinf(a).sum()),'fraction':float((~np.isfinite(a)).mean())} for name,a in [('IMAGE',image),('VARIANCE',variance)]},'variance_statistics':stats,'sqrt_variance_statistics':noise,'variance_statistics_selection':'analysis_mask True; no correction for correlations or unmodeled errors','numerically_positive_variance_count':int(positive.sum()),'flag_definitions':definitions,'reason_counts':{'image_nonfinite':int(image_invalid.sum()),'variance_invalid':int(variance_invalid.sum()),'critical_flags':int(critical.sum()),'unknown_flags':int(unknown.sum()),'source_background_only':int(source.sum()),'caution_background_only':int(caution.sum())}}
    if zodi is None:
        metrics['zodi']={'available':False};warnings.append('ZODI unavailable')
    else:
        if zodi.shape!=image.shape:raise ValueError('ZODI shape mismatch')
        finite=np.isfinite(zodi);metrics['zodi']={'available':True,'finite_count':int(finite.sum()),'nonfinite_count':int((~finite).sum()),'nonfinite_fraction':float((~finite).mean()),'statistics':summary(zodi[finite]),'subtracted':False}
        if not finite.all():warnings.append('Nonfinite ZODI values; no automatic analysis exclusion')
    if not background.any():warnings.append('No background candidates; no background estimate possible from this mask alone')
    if image_invalid.any() or variance_invalid.any():warnings.append('Invalid numeric pixels excluded')
    masks={'analysis_mask':analysis,'background_mask':background,'analysis_exclusion_reasons':reasons,'background_exclusion_reasons':background_reasons}
    return masks,metrics,warnings

def evaluate_quality(extraction:str|Path,technical_report:str|Path,*,output_dir:str|Path|None=None)->tuple[dict,Path]:
    extraction=Path(extraction).resolve();technical_report=Path(technical_report).resolve()
    folder=Path(output_dir) if output_dir else ROOT/'data'/'quality'
    folder=folder/str(uuid.uuid4());folder.mkdir(parents=True)
    report={'quality_status':'failed','evaluation_timestamp':datetime.now(timezone.utc).isoformat(),'quality_policy_version':POLICY_VERSION,'technical_validation_reference':str(technical_report),'extraction_reference':str(extraction),'warnings':[],'errors':[]};metrics={}
    try:
        technical=json.loads(technical_report.read_text());metadata=json.loads((extraction/'metadata.json').read_text())
        if technical.get('overall_technical_status') not in ('passed','passed_with_warnings') or technical.get('errors') or technical.get('eligible_for_scientific_quality_validation') is not True:raise ValueError('Critical technical validation failure; quality evaluation refused')
        if Path(technical['extraction_reference']).resolve()!=extraction:raise ValueError('Technical extraction reference mismatch')
        for key in ('request_id','product_id','observation_id'):
            if metadata.get(key)!=technical.get(key):raise ValueError('Identity mismatch '+key)
            report[key]=metadata.get(key)
        recorded=technical['provenance_checks']['extraction_file_sha256']
        for name in ('arrays.npz','tables.fits','metadata.json','report.json'):
            if digest(extraction/name)!=recorded.get(name):raise ValueError('Input changed since technical validation: '+name)
        header=fits.Header.fromstring(next(x['cards'] for x in metadata['headers'] if x['name']=='FLAGS'),sep='\n')
        with np.load(extraction/'arrays.npz',allow_pickle=False) as data:
            masks,metrics,warnings=evaluate_pixels(data['IMAGE'],data['VARIANCE'],data['FLAGS'],header,data['ZODI'] if 'ZODI' in data else None)
        report['warnings'].extend(warnings)
        if not metrics['analysis_usable_pixels']:report['errors'].append('No analysis-usable pixels under VEGA policy')
        extensions={e['name']:e for e in metadata['extensions']}
        metrics['units']={'variance':extensions['VARIANCE']['unit'],'sqrt_variance':str(u.Unit(extensions['VARIANCE']['unit'])**0.5),'zodi':extensions.get('ZODI',{}).get('unit')}
        report.update(processing_version=metadata.get('processing_version'),collection=metadata.get('collection'),flag_definitions_source={'header':'Original FLAGS MSKNnnnn/MSKDnnnn in hash-bound metadata','reference':REFERENCE,'reference_table':'Current tutorial compared by name AND bit; not a blanket version-independent mapping'},mask_shape=list(masks['analysis_mask'].shape),mask_dtype='bool',true_means={'analysis_mask':'accepted by stated VEGA policy','background_mask':'candidate for later background estimation'},reason_encoding={'1':'IMAGE nonfinite','2':'VARIANCE nonfinite or <=0','4':'critical flag','8':'unknown bit','16':'SOURCE (background only)','32':'caution flag (background only)'},technical_capabilities=technical.get('capabilities'),pixel_counts={k:metrics[k] for k in ('total_pixels','analysis_usable_pixels','analysis_usable_fraction','background_candidate_pixels','background_candidate_fraction')})
        np.savez(folder/'masks.npz',**masks)
        with np.load(folder/'masks.npz',allow_pickle=False) as reread:
            if not all(np.array_equal(reread[k],v) for k,v in masks.items()):raise ValueError('Mask readback mismatch')
        for name in recorded:
            if digest(extraction/name)!=recorded[name]:raise ValueError('Input changed during quality evaluation')
        report['quality_status']='failed' if report['errors'] else ('passed_with_warnings' if report['warnings'] else 'passed')
        report['ready_for_analysis_readiness']=not report['errors']
    except Exception as exc:report['errors'].append(str(exc));report['ready_for_analysis_readiness']=False
    (folder/'quality_metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False),encoding='utf-8')
    (folder/'quality_report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    return report,folder

