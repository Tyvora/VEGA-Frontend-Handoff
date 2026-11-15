"""Live SIA metadata tests A/B/D and bounded north ecliptic pole test C."""
import json
from astropy.coordinates import SkyCoord, BarycentricMeanEcliptic
from astropy import units as u
from user_input import create_request
from request_validation import validate_request
from archive_search import search,save_results,SIASettings

def main():
    r=create_request('coordinates',{'ra':210.80227,'dec':54.34895},'sky_viewer')
    acceptance,_=validate_request(r)
    catalog,report=search(r,acceptance,settings=SIASettings(maxrec=10000,timeout=45,retries=0))
    folder=save_results(catalog,report)
    print(json.dumps({'folder':str(folder),'status':report['status'],'counts':report['queries'],'unique':report['number_of_unique_products'],'eligible':sum(p['downloadable'] for p in catalog['products'])}),flush=True)
    pole=SkyCoord(lon=0*u.deg,lat=90*u.deg,frame=BarycentricMeanEcliptic(equinox='J2000')).icrs
    r=create_request('coordinates',{'ra':float(pole.ra.deg),'dec':float(pole.dec.deg)},'sky_viewer',fov_deg=.001)
    acceptance,_=validate_request(r)
    catalog,report=search(r,acceptance,settings=SIASettings(maxrec=100,timeout=45,retries=0),collections=['spherex_dr1_deep','spherex_qr3_deep'])
    report['position_reference']='North ecliptic pole: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf ; J2000 ecliptic pole transformed with Astropy'
    folder=save_results(catalog,report)
    print(json.dumps({'folder':str(folder),'status':report['status'],'counts':report['queries'],'unique':report['number_of_unique_products']}),flush=True)
if __name__=='__main__': main()
