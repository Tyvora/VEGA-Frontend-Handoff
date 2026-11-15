import copy
import numpy as np
import pytest
from analysis_readiness.policy import assess,Policy,temporal
from analysis_readiness.readiness import distribution

@pytest.fixture
def facts():
    # Synthetic evidence: well sampled spatial image, no verified calibration products.
    return {'product_id':'synthetic-product','observation_id':'obs1','observation_time':60000.,'bandpass':'SPHEREx-D3','image':True,'variance':True,'units':True,'wcs':True,'epsf':True,'spectral_table':True,'spectral_maps':False,'noise':True,'analysis_pixels':90,'analysis_fraction':.9,'background_pixels':40,'background_fraction':.4,'background_occupied_fraction':1.,'analysis_occupied_fraction':1.,'references':{'fixture':'synthetic'}}

def test_display_and_gates(facts):
    r=assess([facts]);assert r['sky_visualization']['status']=='ready'
    assert r['source_detection']['status']=='conditional'
    assert r['source_detection']['allow_preparation'] and not r['source_detection']['allow_scientific_execution']
    assert r['background_estimation']['status']=='conditional' # No estimator qualified.
    assert not r['photometry']['methods']['calibrated_flux']['allow_scientific_execution']

@pytest.mark.parametrize('field,capability,reason',[('wcs','sky_visualization','SPATIAL_WCS_MISSING'),('image','sky_visualization','IMAGE_MISSING'),('variance','source_detection','VARIANCE_MISSING'),('noise','source_detection','NOISE_INFORMATION_MISSING'),('units','photometry','UNITS_UNVERIFIED')])
def test_missing_requirements(facts,field,capability,reason):
    facts[field]=False;r=assess([facts])[capability]
    assert r['status']=='blocked' and reason in r['reason_codes'] and not r['allow_preparation']

def test_insufficient_background_not_global_detection_veto(facts):
    facts.update(background_pixels=20,background_fraction=.0058,background_occupied_fraction=.1875)
    r=assess([facts]);assert r['background_estimation']['status']=='blocked'
    assert r['source_detection']['status']=='conditional'
    assert 'BACKGROUND_SPATIALLY_CLUSTERED' in r['background_estimation']['reason_codes']

def test_spatial_distribution_independent_expected():
    mask=np.zeros((8,8),bool);mask[:2,:2]=True
    r=distribution(mask,4)
    assert r['cell_counts']==[4]+[0]*15 and r['occupied_fraction']==1/16

def test_configurable_background_policy(facts):
    facts.update(background_pixels=20,background_fraction=.1,background_occupied_fraction=.5)
    r=assess([facts],Policy(min_background_pixels=10))
    assert r['background_estimation']['reason_codes']==['BACKGROUND_ESTIMATOR_UNSPECIFIED']

def test_missing_epsf_and_spectral_maps(facts):
    facts['epsf']=False;r=assess([facts])
    assert 'EPSF_MISSING' in r['photometry']['methods']['calibrated_flux']['reason_codes']
    assert r['spectral_analysis']['status']=='blocked'
    assert r['spectral_analysis']['evidence']['spectral_table_valid']

@pytest.mark.parametrize('variant,reason',[('single','SECOND_INDEPENDENT_OBSERVATION_MISSING'),('band','BANDPASSES_INCOMPATIBLE'),('time','OBSERVATION_TIME_MISSING'),('sameobs','SECOND_INDEPENDENT_OBSERVATION_MISSING')])
def test_temporal_independence(facts,variant,reason):
    other=dict(facts,product_id='second',observation_id='obs2',observation_time=60001.)
    rows=[facts,other]
    if variant=='single':rows=[facts]
    if variant=='band':other['bandpass']='SPHEREx-D2'
    if variant=='time':other['observation_time']=None
    if variant=='sameobs':other['observation_id']='obs1'
    r=temporal(rows);assert r['status']=='blocked' and reason in r['reason_codes']

def test_multiple_compatible_not_automatically_science_ready(facts):
    other=dict(facts,product_id='second',observation_id='obs2',observation_time=60001.)
    r=temporal([facts,other]);assert r['status']=='conditional' and not r['allow_scientific_execution']
