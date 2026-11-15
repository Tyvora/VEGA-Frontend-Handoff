import numpy as np
import pytest
from astropy.io import fits
from scientific_quality_validation import evaluate_pixels
from scientific_quality_validation.policy import EXPECTED

def header():
    h=fits.Header()
    for bit,name in EXPECTED.items():h[f'MSKN{bit:04d}']=name
    return h

def evaluate(flags,image=None,variance=None):
    flags=np.array(flags,dtype=np.int32).reshape(1,-1)
    image=np.ones(flags.shape) if image is None else np.array(image,dtype=float).reshape(flags.shape)
    variance=np.ones(flags.shape)*4 if variance is None else np.array(variance,dtype=float).reshape(flags.shape)
    return evaluate_pixels(image,variance,flags,header())

def test_source_critical_warning_information():
    masks,metrics,w=evaluate([0,1<<21,1<<6,1<<19,1<<12,(1<<21)|(1<<6)])
    assert masks['analysis_mask'].tolist()==[[True,True,False,True,True,False]]
    assert masks['background_mask'].tolist()==[[True,False,False,False,True,False]]
    assert metrics['category_pixel_counts']['critical']==2
    assert metrics['category_pixel_counts']['source_background_exclusion']==2
    assert metrics['sqrt_variance_statistics']['median']==2

@pytest.mark.parametrize('flag',[1<<3,1<<30,-2147483648])
def test_unknown_bits(flag):
    masks,metrics,w=evaluate([flag])
    assert not masks['analysis_mask'][0,0] and metrics['category_pixel_counts']['unknown']==1

@pytest.mark.parametrize('value',[np.nan,np.inf,-np.inf])
def test_nonfinite_image(value):
    masks,m,w=evaluate([0],image=[value])
    assert not masks['analysis_mask'].any()

@pytest.mark.parametrize('value',[0,-1,np.nan,np.inf,-np.inf])
def test_invalid_variance(value):
    masks,m,w=evaluate([0],variance=[value])
    assert not masks['analysis_mask'].any() and m['invalid_variance_count']==1

def test_no_mutation_and_zodi():
    image=np.ones((2,3));variance=image*4;flags=np.zeros((2,3),dtype='>i4');zodi=image.copy();zodi[0,0]=np.nan
    original=[a.copy() for a in (image,variance,flags,zodi)]
    masks,m,w=evaluate_pixels(image,variance,flags,header(),zodi)
    for a,b in zip((image,variance,flags,zodi),original):np.testing.assert_array_equal(a,b)
    assert masks['analysis_mask'].shape==(2,3) and masks['analysis_mask'].dtype==bool
    assert m['zodi']['nonfinite_count']==1 and m['zodi']['subtracted'] is False

def test_definition_conflict():
    h=header();h['MSKN0021']='NOT_SOURCE'
    masks,m,w=evaluate_pixels(np.ones((1,1)),np.ones((1,1)),np.array([[1<<21]],dtype=np.int32),h)
    assert not masks['analysis_mask'].any() and w
