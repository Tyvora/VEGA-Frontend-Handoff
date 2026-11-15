"""Loss-preserving FITS extraction, without scientific validation."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import hashlib,json,math,uuid
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales

ROOT=Path(__file__).resolve().parent.parent
ARRAYS=('IMAGE','VARIANCE','FLAGS','ZODI')
TABLES=('EPSF','WCS-WAVE')
@dataclass(frozen=True)
class ExtractionLimits:
    max_file_bytes:int=256*1024*1024
    max_array_bytes:int=512*1024*1024

def sha256(path:Path)->str:
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def extract(manifest_path:str|Path, product_id:str, *, root:Path=ROOT, limits:ExtractionLimits=ExtractionLimits())->tuple[dict,Path]:
    root=Path(root).resolve()
    output=root/'data'/'extractions'/str(uuid.uuid4());output.mkdir(parents=True)
    report={'status':'failed','extraction_timestamp':datetime.now(timezone.utc).isoformat(),'product_id':product_id,'extracted':[],'missing':[],'warnings':[],'errors':[]}
    metadata={'schema_version':'1.0','extensions':[],'celestial_wcs':{'status':'unavailable'},'spectral_wcs':{'status':'tables_only','derived_maps_available':False,'reason':'Cutout-to-parent spectral calibration offsets have not been independently verified; no derived wavelength/bandwidth maps generated.'}}
    try:
        manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        entries=[entry for entry in manifest['entries'] if entry.get('product_id')==product_id and entry.get('download_status')=='downloaded']
        if len(entries)!=1:raise ValueError('Expected one downloaded product in manifest')
        entry=entries[0];source=Path(entry['local_file_path']).resolve()
        if not (source.is_relative_to(root/'data'/'raw') or source.is_relative_to(root/'data'/'cutouts')):raise ValueError('Source outside pipeline storage')
        if source.stat().st_size>limits.max_file_bytes:raise ValueError('Source exceeds resource limit')
        digest=sha256(source)
        if digest!=entry.get('sha256') or source.stat().st_size!=entry.get('file_size'):raise ValueError('Manifest integrity mismatch')
        if manifest.get('request_id')!=entry.get('request_id'):raise ValueError('Manifest request identity mismatch')
        metadata.update(request_id=entry['request_id'],product_id=product_id,observation_id=entry.get('observation_id'),collection=entry.get('collection'),detector=None,processing_version=None,source_fits_path=str(source),source_sha256=digest,download_manifest=str(Path(manifest_path).resolve()),download_entry=entry,extraction_timestamp=report['extraction_timestamp'])
        arrays={};tables=[];used=0
        with fits.open(source,memmap=False,lazy_load_hdus=False) as hdus:
            metadata['headers']=[{'index':i,'name':h.name,'cards':h.header.tostring(sep='\n',endcard=True,padding=False)} for i,h in enumerate(hdus)]
            metadata['processing_version']=hdus[0].header.get('VERSION')
            for name in ARRAYS+TABLES:
                matches=[(i,h) for i,h in enumerate(hdus) if h.name==name]
                if not matches:report['missing'].append(name);continue
                if len(matches)!=1:raise ValueError('Ambiguous extension '+name)
                index,hdu=matches[0]
                if name in ARRAYS:
                    if not isinstance(hdu,(fits.ImageHDU,fits.CompImageHDU)):raise ValueError('Unexpected image HDU '+name)
                    expected=math.prod(hdu.shape)*max(1,abs(hdu.header.get('BITPIX',8))//8)
                    if used+expected>limits.max_array_bytes:raise ValueError('Expanded array resource limit')
                elif not isinstance(hdu,(fits.BinTableHDU,fits.TableHDU)):raise ValueError('Unexpected table HDU '+name)
                data=hdu.data
                if data is None or data.size==0:report['warnings'].append('Empty extension '+name);report['missing'].append(name);continue
                used+=data.nbytes
                if used>limits.max_array_bytes:raise ValueError('Array resource limit')
                info={'name':name,'hdu_index':index,'hdu_type':type(hdu).__name__,'shape':list(data.shape),'dtype':str(data.dtype),'unit':hdu.header.get('BUNIT')}
                if name in ARRAYS:
                    arrays[name]=np.array(data,copy=True)
                    if name=='FLAGS' and arrays[name].dtype.kind not in 'iu':raise ValueError('FLAGS is not an integer array')
                else:
                    tables.append(hdu.copy())
                    info['columns']=[{'name':c.name,'format':c.format,'unit':c.unit,'dim':c.dim} for c in hdu.columns]
                metadata['extensions'].append(info);report['extracted'].append(name)
            if 'IMAGE' in arrays:
                header=hdus['IMAGE'].header
                if header.get('OBSID') is not None and entry.get('observation_id') is not None and header['OBSID']!=entry['observation_id']:raise ValueError('Observation identity mismatch')
                detector=header.get('DETECTOR');metadata['detector']=detector
                expected_detector=entry.get('source_metadata',{}).get('detector')
                if detector is not None and expected_detector is not None and str(detector)!=str(expected_detector).removeprefix('D'):raise ValueError('Detector identity mismatch')
                metadata['observation_metadata']={k:header.get(k) for k in ('OBSID','DETECTOR','DATE-OBS','MJD-OBS','DATE-BEG','DATE-END','MJD-BEG','MJD-END','TIMESYS','XPOSURE','RADESYS')}
                try:
                    if not all(k in header for k in ('CTYPE1','CTYPE2','CRPIX1','CRPIX2','CRVAL1','CRVAL2')):raise ValueError('Incomplete celestial WCS header')
                    wcs=WCS(header,fobj=hdus).celestial
                    if not wcs.has_celestial:raise ValueError('No celestial axes')
                    ny,nx=arrays['IMAGE'].shape
                    sky=wcs.pixel_to_world_values([0,(nx-1)/2,nx-1],[0,(ny-1)/2,ny-1])
                    metadata['celestial_wcs']={'status':'available','frame':header.get('RADESYS'),'header':wcs.to_header(relax=True).tostring(sep='\n',padding=False),'reference_pixel_fits_1based':wcs.wcs.crpix.tolist(),'reference_world_deg':wcs.wcs.crval.tolist(),'projection_plane_pixel_scale_deg_at_reference':proj_plane_pixel_scales(wcs).tolist(),'array_shape':[ny,nx],'sample_pixel_origin':0,'sample_pixels':[[0,0],[(nx-1)/2,(ny-1)/2],[nx-1,ny-1]],'sample_world_deg':np.array(sky).T.tolist(),'has_sip':wcs.sip is not None}
                except Exception as exc:report['warnings'].append('Celestial WCS unavailable: '+str(exc))
            np.savez(output/'arrays.npz',**arrays)
            fits.HDUList([hdus[0].copy()]+tables).writeto(output/'tables.fits',overwrite=False)
        with np.load(output/'arrays.npz',allow_pickle=False) as saved:
            for name,array in arrays.items():
                if saved[name].dtype!=array.dtype or not np.array_equal(saved[name],array,equal_nan=True):raise ValueError('Array readback mismatch')
        with fits.open(output/'tables.fits',memmap=False) as saved:
            for original in tables:
                restored=saved[original.name]
                if original.header.tostring()!=restored.header.tostring():report['warnings'].append('FITS serialization normalized table header '+original.name)
                for col in original.columns.names:
                    for a,b in zip(original.data[col],restored.data[col]):
                        if not np.array_equal(a,b,equal_nan=np.asarray(a).dtype.kind in 'fc'):raise ValueError('Table readback mismatch '+original.name+'/'+col)
        if sha256(source)!=digest:raise ValueError('Source changed during extraction')
        report['readback_verified']=True
        report['status']='partial' if report['missing'] else 'completed'
        report['warnings'].append(metadata['spectral_wcs']['reason'])
    except Exception as exc:report['errors'].append(str(exc))
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2,allow_nan=False),encoding='utf-8')
    (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    return report,output

