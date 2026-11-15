import numpy as np
from analysis_readiness.readiness import distribution

def test_equal_counts_different_spatial_support():
    clustered=np.zeros((8,8),bool);clustered[:2,:2]=True
    spread=np.zeros((8,8),bool);spread[0,0]=spread[0,7]=spread[7,0]=spread[7,7]=True
    assert clustered.sum()==spread.sum()==4
    assert distribution(clustered,4)['occupied_fraction']==1/16
    assert distribution(spread,4)['occupied_fraction']==4/16
