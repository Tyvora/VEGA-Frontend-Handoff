"""Technical checks only; no masks, calibration, extraction or science decisions."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,uuid
import numpy as np
from astropy import units as u
from astropy.io import fits
from astropy.wcs import WCS
ROOT=Path(__file__).resolve().parent.parent
@dataclass(frozen=True)
class Settings:
    roundtrip_tolerance_px:float=0.001
    grid_size:int=5
    max_bytes:int=512*1024*1024
    def __post_init__(self):
        if not np.isfinite(self.roundtrip_tolerance_px) or self.roundtrip_tolerance_px<=0 or not 2<=self.grid_size<=32 or self.max_bytes<=0:raise ValueError('Invalid validation settings')

def digest(path:Path)->str:
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def array_checks(arrays:dict,extensions:list)->tuple[dict,list]:
    errors=[];checks={};info={e['name']:e for e in extensions}
    for name in ('IMAGE','VARIANCE','FLAGS','ZODI'):
        if name not in arrays:
            if name!='ZODI':errors.append(('missing_required_data',name,'Missing required array'))
            continue
        a=arrays[name]
        checks[name]={'shape':list(a.shape),'dtype':str(a.dtype),'size':int(a.size)}
        if a.ndim!=2 or not a.size:errors.append(('critical_structure',name,'Expected nonempty 2D array'))
        if a.dtype.kind not in ('iu' if name=='FLAGS' else 'f'):errors.append(('critical_structure',name,'Invalid dtype'))
        if name in info and (list(a.shape)!=info[name]['shape'] or str(a.dtype)!=info[name]['dtype']):errors.append(('critical_structure',name,'Shape/dtype differs from extraction metadata'))
        if a.dtype.kind in 'fiu':
            nan=int(np.isnan(a).sum());inf=int(np.isinf(a).sum())
            checks[name].update(nan_count=nan,inf_count=inf,nonfinite_fraction=(nan+inf)/a.size if a.size else None)
        if 'IMAGE' in arrays and a.shape!=arrays['IMAGE'].shape:errors.append(('critical_structure',name,'Shape differs from IMAGE'))
    return checks,errors

def unit_checks(extensions:list)->tuple[dict,list]:
    checks={};errors=[];info={e['name']:e for e in extensions}
    for name,target in [('IMAGE',u.MJy/u.sr),('VARIANCE',(u.MJy/u.sr)**2),('ZODI',u.MJy/u.sr)]:
        if name=='ZODI' and name not in info:continue
        text=info.get(name,{}).get('unit')
        try:
            if not text:raise ValueError('Missing unit')
            unit=u.Unit(text)
            if not unit.is_equivalent(target):raise ValueError('Incompatible unit')
            checks[name]={'valid':True,'original_unit':text}
        except Exception as exc:
            checks[name]={'valid':False,'original_unit':text};errors.append(('invalid_units',name,str(exc)))
    if info.get('FLAGS',{}).get('unit') not in (None,''):errors.append(('invalid_units','FLAGS','FLAGS must not have a physical unit'))
    return checks,errors

def check_wcs(header:str,shape:tuple,settings:Settings)->dict:
    h=fits.Header.fromstring(header,sep='\n')
    if not all(k in h for k in ('CTYPE1','CTYPE2','CRPIX1','CRPIX2','CRVAL1','CRVAL2')):raise ValueError('Incomplete WCS header')
    w=WCS(h).celestial
    if not w.has_celestial:raise ValueError('No celestial WCS')
    ny,nx=shape
    x,y=np.meshgrid(np.linspace(0,nx-1,settings.grid_size),np.linspace(0,ny-1,settings.grid_size))
    pixels=np.vstack([np.column_stack([x.ravel(),y.ravel()]),[(nx-1)/2,(ny-1)/2]])
    sky=w.all_pix2world(pixels,0)
    if not np.isfinite(sky).all() or not ((sky[:,0]>=0)&(sky[:,0]<360)&(abs(sky[:,1])<=90)).all():raise ValueError('Invalid sky coordinates')
    back=w.all_world2pix(sky,0,tolerance=min(settings.roundtrip_tolerance_px/10,1e-8),maxiter=100,detect_divergence=True)
    error=float(np.max(np.linalg.norm(back-pixels,axis=1)))
    if not np.isfinite(error) or error>settings.roundtrip_tolerance_px:raise ValueError('Roundtrip exceeds pixel tolerance: '+str(error))
    return {'valid':True,'max_roundtrip_error_px':error,'tolerance_px':settings.roundtrip_tolerance_px,'number_of_points':len(pixels),'pixel_order':'x=column, y=row; origin=0','has_sip':w.sip is not None,'center_world_deg':sky[-1].tolist()}

def check_wave(hdu)->dict:
    if not isinstance(hdu,fits.BinTableHDU) or hdu.data is None or len(hdu.data)!=1:raise ValueError('Expected one-row WCS-WAVE binary table')
    if not {'X','Y','VALUES'}<=set(hdu.columns.names):raise ValueError('Missing X/Y/VALUES')
    x,y,v=(hdu.data[k][0] for k in ('X','Y','VALUES'))
    if x.ndim!=1 or y.ndim!=1 or len(x)<2 or len(y)<2 or v.shape!=(len(y),len(x),2):raise ValueError('Inconsistent lookup dimensions')
    if not all(np.isfinite(a).all() for a in (x,y,v)) or not (np.diff(x)>0).all() or not (np.diff(y)>0).all():raise ValueError('Invalid lookup values or coordinate ordering')
    return {'valid':True,'x_length':len(x),'y_length':len(y),'values_shape':list(v.shape),'columns':[{'name':c.name,'format':c.format,'dim':c.dim,'unit':c.unit} for c in hdu.columns]}

def check_epsf(hdu)->dict:
    required={'BINX','BINY','XCENTER','YCENTER','XWIDTH','YWIDTH','NSTAR','NEFF_MEAN','CWAVE','CBAND','EPSF'}
    if not isinstance(hdu,fits.BinTableHDU) or hdu.data is None or not len(hdu.data) or not required<=set(hdu.columns.names):raise ValueError('Missing EPSF data/columns')
    psf=hdu.data['EPSF']
    if psf.ndim!=3 or min(psf.shape)<1 or psf.dtype.kind!='f':raise ValueError('Invalid EPSF shape/type')
    for name in required:
        values=hdu.data[name]
        if values.dtype.kind not in 'fiu' or not np.isfinite(values).all():raise ValueError('Invalid EPSF values: '+name)
    for name in ('BINX','BINY','NSTAR'):
        if hdu.data[name].dtype.kind not in 'iu':raise ValueError('Invalid EPSF integer field '+name)
    return {'valid':True,'rows':len(hdu.data),'psf_shape':list(psf.shape),'detector':hdu.header.get('DETECTOR')}

def validate_extraction(folder:str|Path,*,settings:Settings=Settings(),output_dir:Path|None=None)->tuple[dict,Path]:
    folder=Path(folder).resolve();errors=[];warnings=[]
    report={'schema_version':'1.0','request_id':None,'product_id':None,'observation_id':None,'extraction_reference':str(folder),'validation_timestamp':datetime.now(timezone.utc).isoformat(),'array_checks':{},'units_checks':{},'wcs_checks':{},'spectral_metadata_checks':{},'epsf_checks':{},'provenance_checks':{},'errors':errors,'warnings':warnings,'capabilities':{'spatial_wcs_available':False,'spectral_table_valid':False,'spectral_maps_available':False,'epsf_available':False}}
    def error(category,field,message):errors.append({'category':category,'field':field,'message':str(message)})
    try:
        for name in ('arrays.npz','tables.fits','metadata.json','report.json'):
            if not (folder/name).is_file():raise ValueError('Missing file '+name)
            if (folder/name).stat().st_size>settings.max_bytes:raise ValueError('File resource limit '+name)
        m=json.loads((folder/'metadata.json').read_text());er=json.loads((folder/'report.json').read_text())
        for key in ('request_id','product_id','observation_id'):report[key]=m.get(key)
        for key in ('request_id','product_id'):
            if not m.get(key):error('missing_required_data',key,'Missing required identity')
        if er.get('status')=='failed':error('critical_structure','extraction_report','Extraction failed')
        if er.get('product_id')!=m.get('product_id'):error('provenance_mismatch','product_id','Report identity mismatch')
        manifest=json.loads(Path(m['download_manifest']).read_text())
        matches=[e for e in manifest['entries'] if e.get('product_id')==m.get('product_id') and e.get('download_status')=='downloaded']
        if len(matches)!=1:raise ValueError('No unambiguous downloaded manifest entry')
        e=matches[0]
        for key in ('product_id','observation_id','request_id','collection'):
            if m.get(key) is None:warnings.append({'category':'incomplete_optional_metadata','field':key,'message':'Identity metadata unavailable'})
            elif m[key]!=e.get(key):error('provenance_mismatch',key,'Manifest identity mismatch')
        if manifest.get('request_id')!=m.get('request_id'):error('provenance_mismatch','request_id','Manifest root mismatch')
        if e.get('sha256')!=m.get('source_sha256'):error('integrity_mismatch','source_sha256','Metadata/manifest hash mismatch')
        source=Path(m['source_fits_path'])
        if source.exists():
            actual=digest(source);report['provenance_checks']['source_sha256']=actual
            if actual!=e.get('sha256') or source.stat().st_size!=e.get('file_size'):error('integrity_mismatch','source','Source hash/size mismatch')
        else:warnings.append({'category':'incomplete_optional_metadata','field':'source','message':'Original source unavailable; source hash not checked'})
        report['provenance_checks']['extraction_file_sha256']={name:digest(folder/name) for name in ('arrays.npz','tables.fits','metadata.json','report.json')}
        # Reject zip bombs before numpy materializes members.
        import zipfile
        with zipfile.ZipFile(folder/'arrays.npz') as z:
            if sum(i.file_size for i in z.infolist())>settings.max_bytes:raise ValueError('Expanded NPZ resource limit')
        with np.load(folder/'arrays.npz',allow_pickle=False) as data:arrays={k:data[k] for k in data.files}
        report['array_checks'],issues=array_checks(arrays,m['extensions'])
        for issue in issues:error(*issue)
        report['units_checks'],issues=unit_checks(m['extensions'])
        for issue in issues:error(*issue)
        represented=set(arrays)
        with fits.open(folder/'tables.fits',memmap=False) as tables:
            represented.update(h.name for h in tables[1:])
            for name,func,cap,key in [('WCS-WAVE',check_wave,'spectral_table_valid','spectral_metadata_checks'),('EPSF',check_epsf,'epsf_available','epsf_checks')]:
                try:
                    report[key]=func(tables[name]);report['capabilities'][cap]=True
                    detector=tables[name].header.get('DETECTOR')
                    if detector is not None and m.get('detector') is not None and str(detector)!=str(m['detector']):raise ValueError('Table detector identity mismatch')
                    info=next(x for x in m['extensions'] if x['name']==name)
                    if list(tables[name].data.shape)!=info['shape'] or str(tables[name].data.dtype)!=info['dtype']:raise ValueError('Table shape/dtype differs from extraction metadata')
                    if len(tables[name].columns)!=len(info['columns']):raise ValueError('Table column count mismatch')
                    for c,saved in zip(tables[name].columns,info['columns']):
                        if (c.name,c.format,c.dim,c.unit)!=(saved['name'],saved['format'],saved['dim'],saved['unit']):raise ValueError('Table column metadata mismatch')
                except Exception as exc:
                    report['capabilities'][cap]=False;error('critical_structure',name,exc)
        if represented!=set(er.get('extracted',[])):error('critical_structure','extraction_report','Actual extensions differ from extraction report')
        try:
            report['wcs_checks']=check_wcs(m['celestial_wcs']['header'],arrays['IMAGE'].shape,settings)
            report['capabilities']['spatial_wcs_available']=True
        except Exception as exc:error('invalid_wcs','celestial_wcs',exc)
        warnings.append({'category':'missing_spectral_derived_maps','field':'spectral_maps','message':'No derived maps generated or validated. WCS-WAVE is primarily for visualization; precise spectral work requires appropriate CWAVE/CBAND calibration.'})
        for name,check in report['array_checks'].items():
            if check.get('nan_count',0)+check.get('inf_count',0):warnings.append({'category':'warnings_only','field':name,'message':'Nonfinite pixels recorded; scientific usability not assessed'})
        if source.exists():
            with fits.open(source,memmap=False) as original:
                for name,array in arrays.items():
                    if name not in original or original[name].data.dtype!=array.dtype or not np.array_equal(original[name].data,array,equal_nan=True):error('integrity_mismatch',name,'Extracted array differs from source')
                info={x['name']:x for x in m['extensions']}
                for name in arrays:
                    if name in original and original[name].header.get('BUNIT')!=info.get(name,{}).get('unit'):error('invalid_units',name,'Original BUNIT metadata changed')
                with fits.open(folder/'tables.fits',memmap=False) as copied:
                    for name in ('EPSF','WCS-WAVE'):
                        if name in copied and name in original:
                            for column in copied[name].columns.names:
                                if column not in original[name].columns.names:raise ValueError('Unexpected copied table column')
                                a,b=copied[name].data[column],original[name].data[column]
                                if not np.array_equal(a,b,equal_nan=a.dtype.kind in 'fc'):error('integrity_mismatch',name+'/'+column,'Table data differs from source')
                h=original['IMAGE'].header
                if report['capabilities']['spatial_wcs_available']:
                    source_wcs=WCS(h).celestial
                    ny,nx=arrays['IMAGE'].shape
                    points=[[0,0],[nx-1,0],[0,ny-1],[nx-1,ny-1],[(nx-1)/2,(ny-1)/2]]
                    check=np.array(source_wcs.all_pix2world(points,0))
                    saved_wcs=WCS(fits.Header.fromstring(m['celestial_wcs']['header'],sep='\n')).celestial
                    delta=np.array(saved_wcs.all_pix2world(points,0))-check
                    delta[:,0]=(delta[:,0]+180)%360-180
                    if not np.allclose(delta,0,atol=1e-9):error('invalid_wcs','celestial_wcs','Serialized WCS differs from source center')
                if h.get('OBSID') is not None and h.get('OBSID')!=m.get('observation_id'):error('provenance_mismatch','observation_id','Source OBSID mismatch')
                if h.get('DETECTOR') is not None and str(h['DETECTOR'])!=str(m.get('detector')):error('provenance_mismatch','detector','Source detector mismatch')
    except Exception as exc:error('critical_structure','files',exc)
    report['overall_technical_status']='failed' if errors else ('passed_with_warnings' if warnings else 'passed')
    report['eligible_for_scientific_quality_validation']=not errors
    target=Path(output_dir) if output_dir else ROOT/'data'/'validation';target.mkdir(parents=True,exist_ok=True)
    path=target/('technical-'+str(uuid.uuid4())+'.json')
    with path.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    return report,path



