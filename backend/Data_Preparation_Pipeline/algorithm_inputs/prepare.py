"""Package creation from existing readiness evidence; no readiness recomputation."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
from typing import Any
import json,uuid,zipfile
import numpy as np
from .reader import sha256,read_json,verify_arrays,VALIDATOR,load_package
ROOT=Path(__file__).resolve().parent.parent
VERSION='vega-packaging-1.0'

def prepare_packages(readiness_path:str|Path,*,output_dir:str|Path|None=None,capabilities:list[str]|None=None)->tuple[dict,Path]:
    readiness_path=Path(readiness_path).resolve();r=read_json(readiness_path)
    if r.get('schema_version')!='1.0' or r.get('overall_processing_status')!='completed' or r.get('errors'):raise ValueError('Trusted completed readiness report required')
    if r.get('readiness_policy_version')!='vega-readiness-1.0':raise ValueError('Unsupported readiness policy version')
    records=r.get('evidence',[])
    if not records:raise ValueError('No readiness evidence')
    primary=records[0];refs=primary['references'];extraction=Path(refs['extraction']);quality=Path(refs['quality_validation']);technical=Path(refs['technical_validation'])
    for rec in records:
        for path,digest in rec['input_sha256'].items():
            if sha256(Path(path))!=digest:raise ValueError('Source reference changed since readiness: '+path)
    m=read_json(extraction/'metadata.json');t=read_json(technical);q=read_json(quality/'quality_report.json')
    for key in ('request_id','product_id','observation_id'):
        if key in ('request_id','product_id') and not m.get(key):raise ValueError('Missing product/request identity')
        if any(record.get(key)!=m.get(key) for record in (r,primary,t,q)):raise ValueError('Input identity mismatch: '+key)
    if Path(q['extraction_reference']).resolve()!=extraction.resolve() or Path(q['technical_validation_reference']).resolve()!=technical.resolve():raise ValueError('Quality reference mismatch')
    if t.get('errors') or q.get('errors') or t.get('overall_technical_status') not in ('passed','passed_with_warnings') or q.get('quality_status') not in ('passed','passed_with_warnings'):raise ValueError('Source gates not accepted')
    source=Path(m['source_fits_path']);tables=extraction/'tables.fits'
    if sha256(source)!=m['source_sha256']:raise ValueError('Source FITS mismatch')
    with zipfile.ZipFile(extraction/'arrays.npz') as z:
        if sum(i.file_size for i in z.infolist())>512*1024*1024:raise ValueError('Expanded source arrays exceed resource limit')
    with np.load(extraction/'arrays.npz',allow_pickle=False) as data:arrays={key:data[key] for key in ('IMAGE','VARIANCE','FLAGS','ZODI') if key in data}
    with np.load(quality/'masks.npz',allow_pickle=False) as data:
        for key in ('analysis_mask','background_mask'):arrays[key]=data[key]
    selected=list(r['capabilities']) if capabilities is None else list(capabilities)
    if not selected or len(set(selected))!=len(selected) or any(k not in r['capabilities'] for k in selected):raise ValueError('Unknown/duplicate capability selection')
    for key in selected:
        d=r['capabilities'][key]
        if d.get('policy_version')!=r['readiness_policy_version']:raise ValueError('Decision policy version mismatch')
        if not all(isinstance(d.get(field),list) for field in ('reason_codes','missing_requirements','execution_conditions')):raise ValueError('Missing readiness conditions')
        if d.get('status') not in ('ready','conditional','blocked') or not isinstance(d.get('allow_preparation'),bool) or not isinstance(d.get('allow_scientific_execution'),bool):raise ValueError('Invalid readiness decision')
        if d['status'] in ('conditional','blocked') and d['allow_scientific_execution']:raise ValueError('Contradictory scientific execution gate')
        if d['status']=='blocked' and d['allow_preparation']:raise ValueError('Contradictory preparation gate')
    root=Path(output_dir) if output_dir else ROOT/'data'/'algorithm_inputs';root.mkdir(parents=True,exist_ok=True)
    run_id=str(uuid.uuid4());staging=root/('.staging-'+run_id);staging.mkdir();final=root/run_id
    result={'schema_version':'1.0','preparation_version':VERSION,'readiness_reference':str(readiness_path),'status':'incomplete','packages':{},'unavailable':{},'errors':[]}
    external_files={str(Path(p).resolve()):digest for rec in records for p,digest in rec['input_sha256'].items()}
    external_files[str(readiness_path)]=sha256(readiness_path);external_files[str(source.resolve())]=m['source_sha256']
    external_files[str(tables.resolve())]=sha256(tables)
    try:
        for key in selected:
            d=r['capabilities'][key]
            if d['status']=='blocked' or not d['allow_preparation']:
                result['unavailable'][key]={'reason':'READINESS_PREPARATION_DENIED','decision':d};continue
            if key in ('temporal_comparison','spectral_analysis'):
                raise ValueError('No approved multi-observation/science-spectral package layout yet')
            package=staging/key;package.mkdir()
            references={'extraction':str(extraction.resolve()),'technical_validation':str(technical.resolve()),'quality_validation':str(quality.resolve()),'readiness_report':str(readiness_path),'original_fits':str(source.resolve()),'tables':str(tables.resolve())}
            metadata={'schema_version':'1.0','preparation_version':VERSION,'package_id':str(uuid.uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),'capability':key,**{field:m.get(field) for field in ('request_id','product_id','observation_id','collection','detector','processing_version')},'source_sha256':m['source_sha256'],'references':references,'array_specs':{name:{'shape':list(a.shape),'dtype':str(a.dtype)} for name,a in arrays.items()},'units':{e['name']:e.get('unit') for e in m['extensions'] if e['name'] in arrays},'coordinate_frame':m['celestial_wcs']['frame'],'pixel_axis_order':'arrays[row,column]; WCS(x=column,y=row), origin=0','array_shape':list(arrays['IMAGE'].shape),'wcs_header':m['celestial_wcs']['header'],'observation_metadata':m.get('observation_metadata',{}),'spectral_metadata':{'extraction':m['spectral_wcs'],'technical_capabilities':t['capabilities'],'tables_reference':str(tables.resolve())},'decision':d}
            VALIDATOR.validate(metadata);verify_arrays(arrays,metadata)
            np.savez(package/'arrays.npz',**arrays)
            for name,value in [('metadata.json',metadata),('readiness.json',r)]:
                with (package/name).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False)
            manifest={'schema_version':'1.0','status':'complete','package_id':metadata['package_id'],'preparation_version':VERSION,'files':{name:{'size_bytes':(package/name).stat().st_size,'sha256':sha256(package/name),'content_type':ctype,'source':references['extraction'] if name=='arrays.npz' else str(readiness_path)} for name,ctype in [('arrays.npz','application/x-npz'),('metadata.json','application/json'),('readiness.json','application/json')]},'external_files':[{'path':p,'sha256':digest} for p,digest in external_files.items()]}
            with (package/'manifest.json').open('x',encoding='utf-8') as stream:json.dump(manifest,stream,indent=2)
            with (package/'COMPLETE').open('x',encoding='utf-8') as stream:stream.write(sha256(package/'manifest.json'))
            loaded=load_package(package)
            for name,a in arrays.items():
                if loaded.arrays[name].dtype!=a.dtype or not np.array_equal(loaded.arrays[name],a,equal_nan=True):raise ValueError('Package/source array readback mismatch')
            result['packages'][key]={'path':str((final/key).resolve()),'package_id':metadata['package_id'],'decision':d,'integrity_verified':True}
        for p,digest in external_files.items():
            if sha256(Path(p))!=digest:raise ValueError('Source changed during preparation')
        result['status']='completed'
        with (staging/'preparation_report.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False)
        staging.rename(final)
    except Exception:
        # A failed stage is never published as the final run; retain for diagnosis.
        raise
    return result,final/'preparation_report.json'

