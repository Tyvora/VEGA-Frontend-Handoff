import pytest
from user_input import create_request

def test_icrs_hour_angle_and_diameter():
    request=create_request('coordinates',{'ra':'12h00m00s','dec':'-30d00m00s'},'sky_viewer')
    assert request['ra_deg']==pytest.approx(180)
    assert request['dec_deg']==pytest.approx(-30)
    assert request['coordinate_frame']=='icrs'
    assert request['fov_deg']==0.1 and request['region_shape']=='circle'
