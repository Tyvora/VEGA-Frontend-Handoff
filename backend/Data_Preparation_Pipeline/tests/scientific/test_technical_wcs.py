import numpy as np
from astropy.io import fits
from technical_validation.validate import check_wcs,Settings

def test_polar_roundtrip():
    header=fits.Header({'CTYPE1':'RA---TAN','CTYPE2':'DEC--TAN','CRPIX1':4.,'CRPIX2':3.,'CRVAL1':.001,'CRVAL2':89.99,'CDELT1':-.001,'CDELT2':.001})
    result=check_wcs(header.tostring(sep='\n'),(5,7),Settings())
    assert result['valid'] and result['max_roundtrip_error_px']<.001
    np.testing.assert_allclose(result['center_world_deg'],[.001,89.99],atol=1e-8)
