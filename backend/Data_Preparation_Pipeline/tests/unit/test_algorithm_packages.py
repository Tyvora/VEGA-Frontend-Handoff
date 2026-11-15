import copy,json,shutil
from pathlib import Path
import numpy as np
import pytest
from jsonschema import ValidationError
from algorithm_inputs import prepare_packages,load_package
from algorithm_inputs.reader import VALIDATOR,verify_arrays,sha256
ROOT=Path(__file__).parents[2]
READINESS=ROOT/'data/readiness/2e841b5e-f60b-489a-9e2b-81840a4befda/readiness_report.json'
RUN=ROOT/'data/algorithm_inputs/c40a0dfa-5780-48d5-bea2-ff235c0274c2'

@pytest.fixture
def metadata():return json.loads((RUN/'sky_visualization/metadata.json').read_text())

@pytest.mark.parametrize('key',['IMAGE','VARIANCE','FLAGS','analysis_mask','background_mask'])
def test_required_array(metadata,key):
    package=load_package(RUN/'sky_visualization');arrays=dict(package.arrays);del arrays[key]
    with pytest.raises(ValueError):verify_arrays(arrays,metadata)

@pytest.mark.parametrize('mode',['shape','dtype','mask'])
def test_bad_array(metadata,mode):
    package=load_package(RUN/'sky_visualization');arrays=dict(package.arrays)
    if mode=='shape':arrays['IMAGE']=np.ones((2,2),dtype='>f4')
    if mode=='dtype':arrays['FLAGS']=arrays['FLAGS'].astype(float)
    if mode=='mask':arrays['analysis_mask']=arrays['analysis_mask'].astype(np.int32)
    with pytest.raises(ValueError):verify_arrays(arrays,metadata)

def test_missing_units(metadata):
    del metadata['units']['IMAGE']
    with pytest.raises(ValidationError):VALIDATOR.validate(metadata)

@pytest.mark.parametrize('capability,allowed',[('sky_visualization',True),('source_detection',False),('photometry',False)])
def test_reader_execution_gate(capability,allowed):
    package=load_package(RUN/capability)
    if allowed:assert package.authorize_execution()['authorized']
    else:
        package.metadata['decision']['allow_scientific_execution']=True # caller mutation cannot authorize
        with pytest.raises(PermissionError):package.authorize_execution()

def test_photometry_submethod_denied():
    with pytest.raises(PermissionError):load_package(RUN/'photometry').authorize_execution('calibrated_flux')

@pytest.mark.parametrize('file',['arrays.npz','metadata.json','readiness.json','manifest.json','COMPLETE'])
def test_corruption(tmp_path,file):
    folder=tmp_path/'package';shutil.copytree(RUN/'sky_visualization',folder)
    with (folder/file).open('ab') as f:f.write(b'CORRUPTED')
    with pytest.raises(Exception):load_package(folder)

def test_missing_external_reference(tmp_path):
    folder=tmp_path/'package';shutil.copytree(RUN/'sky_visualization',folder)
    manifest=json.loads((folder/'manifest.json').read_text())
    manifest['external_files'][0]['path']=str(tmp_path/'absent')
    (folder/'manifest.json').write_text(json.dumps(manifest))
    (folder/'COMPLETE').write_text(sha256(folder/'manifest.json'))
    with pytest.raises(ValueError):load_package(folder)

@pytest.mark.parametrize('mode',['identity','gate','report_failed'])
def test_invalid_readiness(tmp_path,mode):
    r=json.loads(READINESS.read_text())
    if mode=='identity':r['product_id']='wrong'
    if mode=='gate':r['capabilities']['source_detection']['allow_scientific_execution']=True
    if mode=='report_failed':r['overall_processing_status']='failed'
    path=tmp_path/'readiness.json';path.write_text(json.dumps(r))
    with pytest.raises(ValueError):prepare_packages(path,output_dir=tmp_path/'out')

@pytest.mark.parametrize('capability',['background_estimation','temporal_comparison','spectral_analysis'])
def test_blocked_no_package(tmp_path,capability):
    report,path=prepare_packages(READINESS,output_dir=tmp_path,capabilities=[capability])
    assert not report['packages'] and capability in report['unavailable'] and not (path.parent/capability).exists()

def test_save_failure_not_published(tmp_path,monkeypatch):
    def fail(*a,**k):raise OSError('disk full')
    monkeypatch.setattr('numpy.savez',fail)
    with pytest.raises(OSError):prepare_packages(READINESS,output_dir=tmp_path)
    assert all(p.name.startswith('.staging-') for p in tmp_path.iterdir())

def test_missing_inputs(tmp_path):
    with pytest.raises(FileNotFoundError):prepare_packages(tmp_path/'missing.json',output_dir=tmp_path)
