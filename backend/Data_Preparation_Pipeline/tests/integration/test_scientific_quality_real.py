import json
from pathlib import Path
import numpy as np
from scientific_quality_validation import evaluate_quality
ROOT=Path(__file__).parents[2]
EXTRACTION=ROOT/'data/extractions/1ff9732e-6d34-47fe-a479-ce385ceeef35'
TECHNICAL=ROOT/'data/validation/technical-a34702f2-8963-4afe-8bb1-6d48ac6c75b6.json'

def test_real_quality(tmp_path):
    r,folder=evaluate_quality(EXTRACTION,TECHNICAL,output_dir=tmp_path)
    metrics=json.loads((folder/'quality_metrics.json').read_text())
    assert r==json.loads((folder/'quality_report.json').read_text())
    assert not r['errors'] and metrics['total_pixels']==3422
    with np.load(folder/'masks.npz') as a:
        assert int(a['analysis_mask'].sum())==metrics['analysis_usable_pixels']
        assert np.all(~a['background_mask']|a['analysis_mask'])

def test_refuse_critical_technical(tmp_path):
    t=json.loads(TECHNICAL.read_text());t['errors']=[{'message':'bad'}]
    path=tmp_path/'technical.json';path.write_text(json.dumps(t))
    r,folder=evaluate_quality(EXTRACTION,path,output_dir=tmp_path/'out')
    assert r['quality_status']=='failed' and not (folder/'masks.npz').exists()

def test_refuse_changed_inputs(tmp_path):
    t=json.loads(TECHNICAL.read_text());t['provenance_checks']['extraction_file_sha256']['arrays.npz']='bad'
    path=tmp_path/'technical.json';path.write_text(json.dumps(t))
    r,folder=evaluate_quality(EXTRACTION,path,output_dir=tmp_path/'out')
    assert r['quality_status']=='failed' and not (folder/'masks.npz').exists()
