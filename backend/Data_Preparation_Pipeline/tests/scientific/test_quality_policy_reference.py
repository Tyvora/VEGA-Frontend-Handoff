import numpy as np
from astropy.io import fits
from scientific_quality_validation import evaluate_pixels

def test_reference_mask_and_variance_distribution():
    # Independent expected values: only source+no-critical pixel survives among first three.
    h=fits.Header({'MSKN0006':'NONFUNC','MSKN0021':'SOURCE','MSKN0012':'FULLSAMPLE'})
    flags=np.array([[64,2097152,0,4096]],dtype=np.int32)
    masks,m,w=evaluate_pixels(np.ones((1,4)),np.array([[1.,9.,0.,16.]]),flags,h)
    np.testing.assert_array_equal(masks['analysis_mask'],[[False,True,False,True]])
    np.testing.assert_array_equal(masks['background_mask'],[[False,False,False,True]])
    assert m['variance_statistics']['minimum']==9
    assert m['variance_statistics']['median']==12.5
    assert m['sqrt_variance_statistics']['median']==3.5
