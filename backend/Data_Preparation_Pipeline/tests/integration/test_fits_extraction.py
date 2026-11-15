import json,hashlib
from pathlib import Path
import numpy as np
import pytest
from astropy.io import fits
from fits_extraction import extract,ExtractionLimits

@pytest.fixture
def source(tmp_path):
    folder=tmp_path/'data/cutouts';folder.mkdir(parents=True)
    path=folder/'test.fits'
    image=fits.ImageHDU(np.arange(12,dtype=np.float32).reshape(3,4),name='IMAGE')
    image.header['BUNIT']='MJy / sr';image.header['OBSID']='obs';image.header['DETECTOR']=3
    image.header.update({'CTYPE1':'RA---TAN','CTYPE2':'DEC--TAN','CRPIX1':1.,'CRPIX2':1.,'CRVAL1':12.,'CRVAL2':30.,'CDELT1':-.001,'CDELT2':.001,'RADESYS':'ICRS'})
    hdus=[fits.PrimaryHDU(),image,fits.ImageHDU(np.full((3,4),2**29,dtype=np.int32),name='FLAGS'),fits.ImageHDU(np.ones((3,4),dtype=np.float32),name='VARIANCE'),fits.ImageHDU(np.zeros((3,4),dtype=np.float32),name='ZODI')]
    for name in ['EPSF','WCS-WAVE']:
        hdus.append(fits.BinTableHDU.from_columns([fits.Column(name='VALUES',format='4E',dim='(2,2)',unit='um',array=[np.ones((2,2))])],name=name))
    fits.HDUList(hdus).writeto(path)
    manifest=tmp_path/'manifest.json'
    entry={'download_status':'downloaded','product_id':'id','request_id':'req','local_file_path':str(path),'file_size':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'observation_id':'obs','source_metadata':{'detector':'D3'},'collection':'test'}
    manifest.write_text(json.dumps({'request_id':'req','entries':[entry]}))
    return manifest,path,tmp_path

def test_arrays_and_tables(source):
    manifest,path,root=source;before=path.read_bytes()
    report,out=extract(manifest,'id',root=root)
    assert report['status']=='completed' and report['readback_verified']
    with fits.open(path) as original,np.load(out/'arrays.npz',allow_pickle=False) as saved:
        for name in ['IMAGE','FLAGS','VARIANCE','ZODI']:
            np.testing.assert_array_equal(saved[name],original[name].data)
            assert saved[name].dtype==original[name].data.dtype
        assert saved['FLAGS'][0,0]==2**29
    metadata=json.loads((out/'metadata.json').read_text())
    assert metadata['extensions'][0]['unit']=='MJy / sr'
    assert metadata['spectral_wcs']['derived_maps_available'] is False
    with fits.open(out/'tables.fits') as tables:assert tables['EPSF'].columns['VALUES'].unit=='um'
    assert path.read_bytes()==before

@pytest.mark.parametrize('mode',['sha','identity','invalid','missing','empty','wrongtype','header','limit'])
def test_errors(source,mode):
    manifest,path,root=source
    record=json.loads(manifest.read_text())
    if mode=='sha':record['entries'][0]['sha256']='bad'
    elif mode=='identity':record['entries'][0]['observation_id']='other'
    elif mode=='invalid':path.write_bytes(b'bad FITS')
    elif mode in ['missing','empty','wrongtype','header']:
        with fits.open(path) as h:hdus=fits.HDUList([x.copy() for x in h])
        if mode=='missing':del hdus['ZODI']
        if mode=='empty':hdus['ZODI'].data=None
        if mode=='wrongtype':hdus[1]=fits.BinTableHDU.from_columns([],name='IMAGE')
        if mode=='header':del hdus['IMAGE'].header['CTYPE1']
        hdus.writeto(path,overwrite=True)
    if mode!='sha':
        record['entries'][0].update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),file_size=path.stat().st_size)
    manifest.write_text(json.dumps(record))
    report,out=extract(manifest,'id',root=root,limits=ExtractionLimits(max_file_bytes=1) if mode=='limit' else ExtractionLimits())
    if mode in ['missing','empty']:assert report['status']=='partial'
    elif mode=='header':assert report['warnings'] and json.loads((out/'metadata.json').read_text())['celestial_wcs']['status']=='unavailable'
    else:assert report['status']=='failed'

def test_real_m101(tmp_path):
    root=Path(__file__).parents[2]
    manifest=root/'data/manifests/22bc3053-7cf8-4786-b187-692a0bf5f218.json'
    report,out=extract(manifest,'ivo://irsa.ipac/spherex_dr1?2025W19_2B_0101_1/D3')
    assert report['status']=='completed' and report['readback_verified']
    with np.load(out/'arrays.npz') as a:assert a['IMAGE'].shape==(59,58) and a['FLAGS'].dtype.kind=='i'
    metadata=json.loads((out/'metadata.json').read_text())
    assert metadata['processing_version']=='7.0.5' and metadata['celestial_wcs']['has_sip']

def test_reference_wcs_from_extraction(source):
    manifest,path,root=source
    report,out=extract(manifest,'id',root=root)
    metadata=json.loads((out/'metadata.json').read_text())
    np.testing.assert_allclose(metadata['celestial_wcs']['sample_world_deg'][0],[12,30],atol=1e-10)

def test_save_failure_report(source,monkeypatch):
    def fail(*a,**k):raise OSError('disk full')
    monkeypatch.setattr('numpy.savez',fail)
    report,out=extract(source[0],'id',root=source[2])
    assert report['status']=='failed' and 'disk full' in report['errors'][0]

def test_array_budget(source):
    report,_=extract(source[0],'id',root=source[2],limits=ExtractionLimits(max_array_bytes=1))
    assert report['status']=='failed'
