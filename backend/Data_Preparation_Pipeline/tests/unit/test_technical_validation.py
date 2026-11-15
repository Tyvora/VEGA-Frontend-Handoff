import json,shutil
from pathlib import Path
import numpy as np
import pytest
from astropy.io import fits
from technical_validation.validate import array_checks,unit_checks,check_wcs,check_wave,check_epsf,Settings,validate_extraction

def arrays():return {'IMAGE':np.ones((3,5),dtype=np.float32),'VARIANCE':np.ones((3,5),dtype=np.float32),'FLAGS':np.ones((3,5),dtype=np.int32)}

def test_arrays_valid_nan():
    a=arrays();a['IMAGE'][0,0]=np.nan;a['VARIANCE'][0,1]=np.inf
    report,errors=array_checks(a,[])
    assert not errors and report['IMAGE']['nan_count']==1 and report['VARIANCE']['inf_count']==1

@pytest.mark.parametrize('name',['IMAGE','VARIANCE','FLAGS'])
def test_missing(name):
    a=arrays();del a[name]
    assert array_checks(a,[])[1]

@pytest.mark.parametrize('name,value',[('FLAGS',np.ones((3,5),dtype=bool)),('IMAGE',np.ones((3,5),dtype=int)),('VARIANCE',np.ones((5,3))),('IMAGE',np.empty((0,5))),('IMAGE',np.ones(15))])
def test_bad_arrays(name,value):
    a=arrays();a[name]=value
    assert array_checks(a,[])[1]

@pytest.mark.parametrize('unit,valid',[('MJy / sr',True),('Jy / sr',True),('m',False),(None,False),('garbage_unit',False)])
def test_units(unit,valid):
    info=[{'name':'IMAGE','unit':unit},{'name':'VARIANCE','unit':'MJy2 / sr2'}]
    checks,errors=unit_checks(info)
    assert checks['IMAGE']['valid']==valid

@pytest.mark.parametrize('sip',[False,True])
def test_wcs_reference_wrap_and_order(sip):
    h=fits.Header({'CTYPE1':'RA---TAN','CTYPE2':'DEC--TAN','CRPIX1':3.,'CRPIX2':2.,'CRVAL1':359.999,'CRVAL2':40.,'CDELT1':-.001,'CDELT2':.001})
    if sip:
        h['CTYPE1']='RA---TAN-SIP';h['CTYPE2']='DEC--TAN-SIP';h['A_ORDER']=2;h['B_ORDER']=2;h['A_2_0']=1e-5;h['B_0_2']=1e-5
    result=check_wcs(h.tostring(sep='\n'),(3,5),Settings())
    # Nonsquare array center (x,y)=(2,1) equals FITS reference pixel.
    np.testing.assert_allclose(result['center_world_deg'],[359.999,40],atol=1e-10)
    assert result['has_sip']==sip and result['max_roundtrip_error_px']<.001

def test_bad_wcs():
    with pytest.raises(ValueError):check_wcs('',(3,5),Settings())

REAL=Path(__file__).parents[2]/'data/extractions/1ff9732e-6d34-47fe-a479-ce385ceeef35'
@pytest.mark.parametrize('name,check',[('EPSF',check_epsf),('WCS-WAVE',check_wave)])
def test_tables(name,check):
    with fits.open(REAL/'tables.fits') as h:
        assert check(h[name])['valid']
    with pytest.raises(ValueError):check(fits.BinTableHDU.from_columns([]))

@pytest.mark.parametrize('mutation',['product','hash','missing','source_path'])
def test_provenance_and_storage(tmp_path,mutation):
    folder=tmp_path/'extraction';shutil.copytree(REAL,folder)
    path=folder/'metadata.json';m=json.loads(path.read_text())
    if mutation=='product':m['product_id']='wrong'
    if mutation=='hash':m['source_sha256']='wrong'
    if mutation=='source_path':m['source_fits_path']=str(tmp_path/'absent.fits')
    if mutation=='missing':(folder/'arrays.npz').unlink()
    path.write_text(json.dumps(m))
    report,p=validate_extraction(folder,output_dir=tmp_path/'reports')
    assert json.loads(p.read_text())==report
    assert (report['overall_technical_status']=='failed') == (mutation!='source_path')
    assert not report['capabilities']['spectral_maps_available']

def test_real_validation(tmp_path):
    report,path=validate_extraction(REAL,output_dir=tmp_path)
    assert report['overall_technical_status']=='passed_with_warnings'
    assert report['capabilities']=={'spatial_wcs_available':True,'spectral_table_valid':True,'spectral_maps_available':False,'epsf_available':True}
    assert report['wcs_checks']['has_sip']
