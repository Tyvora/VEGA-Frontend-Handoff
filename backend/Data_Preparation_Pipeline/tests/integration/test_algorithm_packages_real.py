import json
from pathlib import Path
import numpy as np
from algorithm_inputs import prepare_packages,load_package
from algorithm_inputs.reader import sha256
ROOT=Path(__file__).parents[2]
READINESS=ROOT/'data/readiness/2e841b5e-f60b-489a-9e2b-81840a4befda/readiness_report.json'

def test_real_m101_end_to_end(tmp_path):
    readiness=json.loads(READINESS.read_text())
    before={p:sha256(Path(p)) for p in readiness['evidence'][0]['input_sha256']}
    report,path=prepare_packages(READINESS,output_dir=tmp_path)
    assert json.loads(path.read_text())==report and report['status']=='completed'
    assert set(report['packages'])=={'sky_visualization','source_detection','photometry'}
    source=Path(readiness['extraction_reference']);quality=Path(readiness['quality_validation_reference'])
    with np.load(source/'arrays.npz') as original,np.load(quality/'masks.npz') as masks:
        for capability,entry in report['packages'].items():
            loaded=load_package(entry['path'])
            for name in ('IMAGE','VARIANCE','FLAGS','ZODI'):
                np.testing.assert_array_equal(loaded.arrays[name],original[name]);assert loaded.arrays[name].dtype==original[name].dtype
            for name in ('analysis_mask','background_mask'):np.testing.assert_array_equal(loaded.arrays[name],masks[name])
            assert loaded.metadata['wcs_header']==json.loads((source/'metadata.json').read_text())['celestial_wcs']['header']
            with loaded.open_tables() as tables:assert {'EPSF','WCS-WAVE'}<=set(h.name for h in tables)
    assert before=={p:sha256(Path(p)) for p in before}
