import json
from pathlib import Path
from astropy.wcs import WCS
from astropy.io import fits
import numpy as np
from algorithm_inputs import load_package

def test_wcs_and_surface_brightness_units_preserved():
    root=Path(__file__).parents[2]
    package=load_package(root/'data/algorithm_inputs/c40a0dfa-5780-48d5-bea2-ff235c0274c2/sky_visualization')
    metadata=package.metadata
    assert metadata['units']['IMAGE']=='MJy / sr' and metadata['units']['VARIANCE']=='MJy2 / sr2'
    assert metadata['pixel_axis_order']=='arrays[row,column]; WCS(x=column,y=row), origin=0'
    source=json.loads((Path(metadata['references']['extraction'])/'metadata.json').read_text())
    w=WCS(fits.Header.fromstring(metadata['wcs_header'],sep='\n'))
    # Stored extraction pixel/world reference is independent of package creation.
    pixels=np.array(source['celestial_wcs']['sample_pixels'])
    np.testing.assert_allclose(w.all_pix2world(pixels,0),source['celestial_wcs']['sample_world_deg'],atol=1e-10)
    assert metadata['spectral_metadata']['technical_capabilities']['spectral_maps_available'] is False
