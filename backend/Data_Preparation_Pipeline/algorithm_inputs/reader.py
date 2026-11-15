"""Independent read-only package reader. It never runs algorithms."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib,json,zipfile
import numpy as np
from jsonschema import Draft202012Validator,FormatChecker
SCHEMA=json.loads(Path(__file__).with_name('package_schema.json').read_text(encoding='utf-8-sig'))
VALIDATOR=Draft202012Validator(SCHEMA,format_checker=FormatChecker())
REQUIRED={'IMAGE','VARIANCE','FLAGS','analysis_mask','background_mask'}

def sha256(path:Path)->str:
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def read_json(path:Path)->dict:
    with path.open(encoding='utf-8') as f:return json.load(f)

def verify_arrays(arrays:dict,metadata:dict)->None:
    if not set(arrays)<=(REQUIRED|{'ZODI'}):raise ValueError('Unapproved array names')
    if not REQUIRED<=set(arrays) or set(arrays)!=set(metadata['array_specs']):raise ValueError('Missing/unexpected array')
    shape=tuple(metadata['array_shape'])
    for name,a in arrays.items():
        spec=metadata['array_specs'][name]
        if a.ndim!=2 or not a.size or a.shape!=shape or list(a.shape)!=spec['shape'] or str(a.dtype)!=spec['dtype']:raise ValueError('Array shape/dtype mismatch: '+name)
        kind='b' if name.endswith('_mask') else 'iu' if name=='FLAGS' else 'f'
        if a.dtype.kind not in kind:raise ValueError('Invalid array dtype: '+name)
    if (arrays['background_mask'] & ~arrays['analysis_mask']).any():raise ValueError('Background mask is not subset of analysis mask')

class Package:
    def __init__(self,path:Path,metadata:dict,readiness:dict,arrays:dict):
        self.path,self.metadata,self.readiness,self.arrays=path,metadata,readiness,arrays
    @property
    def decision(self)->dict:return self.metadata['decision']
    def open_tables(self):
        from astropy.io import fits
        fresh=load_package(self.path)
        return fits.open(fresh.metadata['references']['tables'],mode='readonly',memmap=False)
    def authorize_execution(self,method:str|None=None)->dict:
        # Re-open for integrity/decision validation, rather than trusting mutated in-memory metadata.
        fresh=load_package(self.path)
        decision=fresh.decision
        if method is not None:
            decision=decision.get('methods',{}).get(method)
            if decision is None:raise PermissionError('Unknown method scope')
        if decision['status']!='ready' or decision['allow_scientific_execution'] is not True:raise PermissionError('Scientific execution is not authorized: '+str(decision.get('reason_codes')))
        return {'authorized':True,'capability':fresh.metadata['capability'],'method':method,'execution_conditions':decision['execution_conditions']}

def load_package(path:str|Path,*,max_expanded_bytes:int=512*1024*1024)->Package:
    path=Path(path).resolve()
    manifest=read_json(path/'manifest.json')
    if manifest.get('status')!='complete' or manifest.get('schema_version')!='1.0':raise ValueError('Incomplete/unsupported package manifest')
    if (path/'COMPLETE').read_text().strip()!=sha256(path/'manifest.json'):raise ValueError('Manifest completion hash mismatch')
    if set(manifest['files'])!={'arrays.npz','metadata.json','readiness.json'}:raise ValueError('Unexpected package files')
    for name,spec in manifest['files'].items():
        file=path/name
        if file.stat().st_size!=spec['size_bytes'] or sha256(file)!=spec['sha256']:raise ValueError('Package file integrity mismatch: '+name)
    for reference in manifest['external_files']:
        file=Path(reference['path'])
        if not file.is_file() or sha256(file)!=reference['sha256']:raise ValueError('External reference missing or changed: '+str(file))
    metadata=read_json(path/'metadata.json');VALIDATOR.validate(metadata)
    if manifest.get('package_id')!=metadata['package_id']:raise ValueError('Manifest package identity mismatch')
    readiness=read_json(path/'readiness.json')
    if readiness.get('overall_processing_status')!='completed' or readiness.get('errors'):raise ValueError('Readiness evaluation not completed')
    if readiness.get('readiness_policy_version')!='vega-readiness-1.0':raise ValueError('Unsupported readiness policy')
    for key in ('request_id','product_id','observation_id'):
        if metadata[key]!=readiness.get(key):raise ValueError('Package/readiness identity mismatch')
    decision=readiness['capabilities'][metadata['capability']]
    if metadata['decision']!=decision or decision['status']=='blocked' or decision.get('allow_preparation') is not True:raise ValueError('Readiness gate mismatch')
    external={str(Path(r['path']).resolve()):r['sha256'] for r in manifest['external_files']}
    # Verify the package references the exact source report and retained table/FITS files.
    for name in ('readiness_report','tables','original_fits','technical_validation'):
        if str(Path(metadata['references'][name]).resolve()) not in external:raise ValueError('Unbound source reference '+name)
    source_metadata_path=Path(metadata['references']['extraction'])/'metadata.json'
    if str(source_metadata_path.resolve()) not in external:raise ValueError('Extraction metadata not bound to provenance')
    source_metadata=read_json(source_metadata_path)
    for key in ('request_id','product_id','observation_id','collection','detector','processing_version'):
        if source_metadata.get(key)!=metadata[key]:raise ValueError('Source metadata identity mismatch: '+key)
    if metadata['wcs_header']!=source_metadata['celestial_wcs']['header']:raise ValueError('WCS metadata changed')
    for info in source_metadata['extensions']:
        name=info['name']
        if name in metadata['array_specs']:
            if metadata['units'].get(name)!=info['unit'] or metadata['array_specs'][name]!={'shape':info['shape'],'dtype':info['dtype']}:raise ValueError('Original units/array specification changed')
    original=read_json(Path(metadata['references']['readiness_report']))
    if original!=readiness:raise ValueError('Copied readiness differs from source')
    if external[str(Path(metadata['references']['original_fits']).resolve())]!=metadata['source_sha256']:raise ValueError('Original FITS hash mismatch')
    with zipfile.ZipFile(path/'arrays.npz') as archive:
        if sum(i.file_size for i in archive.infolist())>max_expanded_bytes:raise ValueError('Expanded package exceeds memory limit')
    with np.load(path/'arrays.npz',allow_pickle=False) as saved:arrays={k:saved[k] for k in saved.files}
    verify_arrays(arrays,metadata)
    for a in arrays.values():a.setflags(write=False)
    return Package(path,metadata,readiness,arrays)


