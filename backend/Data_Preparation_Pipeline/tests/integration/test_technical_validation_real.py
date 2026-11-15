import json
from pathlib import Path
from technical_validation import validate_extraction

def test_m101_report_roundtrip(tmp_path):
    root=Path(__file__).parents[2]
    folder=root/'data/extractions/1ff9732e-6d34-47fe-a479-ce385ceeef35'
    report,path=validate_extraction(folder,output_dir=tmp_path)
    assert report['eligible_for_scientific_quality_validation']
    assert report==json.loads(path.read_text())
    assert report['array_checks']['IMAGE']['nan_count']==0
