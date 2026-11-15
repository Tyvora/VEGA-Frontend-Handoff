import pytest
from archive_search.sia import parameters,SIASettings,map_product

@pytest.mark.parametrize('ra,dec,expected',[(359.99,0,'CIRCLE 359.99 0 0.05'),(0.01,-90,'CIRCLE 0.01 -90 0.05'),(20,90,'CIRCLE 20 90 0.05')])
def test_spherical_query_delegation(ra,dec,expected):
    assert parameters({'ra_deg':ra,'dec_deg':dec,'fov_deg':.1,'coordinate_frame':'icrs'},'spherex_dr1',SIASettings())['POS']==expected

def test_partial_footprint_retained():
    # Known planar small-angle example: center at RA 0 lies outside 0.02..0.04;
    # radius .05 intersects this footprint. Local code must not center-filter it.
    raw={'s_region':'POLYGON ICRS 0.02 -0.01 0.04 -0.01 0.04 0.01 0.02 0.01','obs_collection':'spherex_dr1'}
    product=map_product(raw,'spherex_dr1')
    assert product['footprint']==raw['s_region']
    assert product['coverage_status']=='intersects; full coverage and valid pixels unverified'
