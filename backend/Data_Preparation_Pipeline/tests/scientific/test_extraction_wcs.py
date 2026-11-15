import json
import numpy as np
from astropy.wcs import WCS
from astropy.io import fits

def test_known_reference_pixel():
    # Analytic reference: zero-based (0,0) = FITS CRPIX (1,1).
    header=fits.Header({'CTYPE1':'RA---TAN','CTYPE2':'DEC--TAN','CRPIX1':1.,'CRPIX2':1.,'CRVAL1':12.,'CRVAL2':30.,'CDELT1':-.001,'CDELT2':.001})
    wcs=WCS(header)
    np.testing.assert_allclose(wcs.pixel_to_world_values(0,0),[12,30],atol=1e-10)
