import json,shutil
from pathlib import Path
import numpy as np
import pytest
from analysis_readiness import evaluate_readiness,InputReferences
from analysis_readiness.readiness import digest
ROOT=Path(__file__).parents[2]
E=ROOT/'data/extractions/1ff9732e-6d34-47fe-a479-ce385ceeef35'
T=ROOT/'data/validation/technical-a34702f2-8963-4afe-8bb1-6d48ac6c75b6.json'
Q=ROOT/'data/quality/7cf8cf36-233b-48ab-9afa-789050bbb3ab'

@pytest.fixture
def refs(tmp_path):
    e=tmp_path/'extract';q=tmp_path/'quality';t=tmp_path/'technical.json'
    shutil.copytree(E,e);shutil.copytree(Q,q)
    technical=json.loads(T.read_text());technical['extraction_reference']=str(e)
    t.write_text(json.dumps(technical))
    quality=json.loads((q/'quality_report.json').read_text());quality.update(extraction_reference=str(e),technical_validation_reference=str(t))
    (q/'quality_report.json').write_text(json.dumps(quality))
    return InputReferences(e,t,q)

def test_real_readiness_and_no_mutation(tmp_path):
    files=[E/'arrays.npz',E/'metadata.json',E/'tables.fits',T,Q/'masks.npz',Q/'quality_report.json']
    before={str(p):digest(p) for p in files}
    r,p=evaluate_readiness([InputReferences(E,T,Q)],output_dir=tmp_path)
    assert r['overall_processing_status']=='completed' and not r['errors']
    assert json.loads(p.read_text())==r
    assert [r['capabilities'][k]['status'] for k in ['sky_visualization','source_detection','background_estimation','photometry','temporal_comparison','spectral_analysis']]==['ready','conditional','blocked','conditional','blocked','blocked']
    assert before=={str(p):digest(p) for p in files}
    assert r['evidence'][0]['analysis_pixels']==3322 and r['evidence'][0]['background_pixels']==20

@pytest.mark.parametrize('mutation,code',[('missing','REPORT_MISSING'),('json','REPORT_MALFORMED_JSON'),('identity','IDENTITY_MISMATCH'),('reference','REFERENCE_MISMATCH'),('technical','TECHNICAL_FAILED'),('quality','QUALITY_FAILED'),('mask_missing','INPUT_UNREADABLE'),('mask_corrupt','INPUT_UNREADABLE'),('policy','QUALITY_POLICY_UNSUPPORTED'),('mask_shape','MASK_INVALID')])
def test_bad_evidence(refs,tmp_path,mutation,code):
    q=Path(refs.quality)/'quality_report.json';t=Path(refs.technical)
    quality=json.loads(q.read_text());technical=json.loads(t.read_text())
    if mutation=='missing':t.unlink()
    elif mutation=='json':q.write_text('{bad')
    elif mutation=='identity':quality['product_id']='wrong';q.write_text(json.dumps(quality))
    elif mutation=='reference':quality['technical_validation_reference']='missing.json';q.write_text(json.dumps(quality))
    elif mutation=='technical':technical['overall_technical_status']='failed';t.write_text(json.dumps(technical))
    elif mutation=='quality':quality['quality_status']='failed';q.write_text(json.dumps(quality))
    elif mutation=='mask_missing':(Path(refs.quality)/'masks.npz').unlink()
    elif mutation=='mask_corrupt':(Path(refs.quality)/'masks.npz').write_bytes(b'corrupt')
    elif mutation=='policy':quality['quality_policy_version']='unknown';q.write_text(json.dumps(quality))
    elif mutation=='mask_shape':
        path=Path(refs.quality)/'masks.npz'
        with np.load(path) as d:arrays={k:d[k] for k in d.files}
        arrays['analysis_mask']=np.zeros((1,1),bool);np.savez(path,**arrays)
    r,p=evaluate_readiness([refs],output_dir=tmp_path/'out')
    assert r['overall_processing_status']=='failed' and r['errors'][0]['reason_code']==code
    assert all(v['status']=='blocked' and not v['allow_scientific_execution'] for v in r['capabilities'].values())
