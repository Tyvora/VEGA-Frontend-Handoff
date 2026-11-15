"""Real existing M101 reuse and package reading, without network."""
from pathlib import Path
import pytest
from orchestrator import run_pipeline,Services
from algorithm_inputs import load_package
ROOT=Path(__file__).parents[2]

def test_existing_m101_reuse_and_resume(tmp_path):
    pid='ivo://irsa.ipac/spherex_dr1?2025W19_2B_0101_1/D3'
    services=Services()
    def no_network(*a,**k):raise AssertionError('Existing product must not be downloaded again')
    services.download_batch=no_network;services.search=no_network
    workflow,path=run_pipeline([pid],request_file=ROOT/'data/requests/c7fe7b2a-55b0-48dc-bcfe-ffdc3853fb70.json',cached_search=ROOT/'data/search_results/d6f57c3e-f6aa-488e-95a7-ac6f1072dd73',reuse_packages={pid:str(ROOT/'data/algorithm_inputs/c40a0dfa-5780-48d5-bea2-ff235c0274c2/preparation_report.json')},services=services,root=tmp_path)
    assert workflow['status']=='completed' and workflow['network_bytes_recorded']==0
    for stage in workflow['products'][pid]['stages'].values():assert stage['status']=='completed' and stage['reused']
    resumed,_=run_pipeline(resume=path,services=services,root=tmp_path)
    assert resumed['status']=='completed' and resumed['run_id']==workflow['run_id']
    for reference in resumed['products'][pid]['package_references']:
        package=load_package(reference)
        assert package.arrays['IMAGE'].shape==(59,58)
        if package.metadata['capability']=='source_detection':
            with pytest.raises(PermissionError):package.authorize_execution()
    assert resumed['products'][pid]['readiness_capabilities']['temporal_comparison']['status']=='blocked'
