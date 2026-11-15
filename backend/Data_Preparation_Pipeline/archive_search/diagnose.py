"""Bounded GET probes, recording full server response; metadata only."""
import json,time,uuid
from pathlib import Path
import requests
BASE="SELECT TOP 2 a.artifactid,a.uri,p.productid,p.energy_bandpassname,p.time_bounds_lower FROM spherex.artifact a JOIN spherex.plane p ON a.planeid=p.planeid WHERE "
QUERIES=[BASE+"1=CONTAINS(POINT('ICRS',279.234734787,38.783688956),p.poly)", BASE+"1=INTERSECTS(p.poly,CIRCLE('ICRS',279.234734787,38.783688956,0.05))",BASE+"1=INTERSECTS(CIRCLE('ICRS',279.234734787,38.783688956,0.05),p.poly)"]
def main():
    folder=Path(__file__).resolve().parent.parent/'data'/'search_results'/('diagnostic-'+str(uuid.uuid4()))
    folder.mkdir()
    records=[]
    for i,q in enumerate(QUERIES):
        start=time.monotonic(); record={'query':q}
        try:
            r=requests.get('https://irsa.ipac.caltech.edu/TAP/sync',params={'REQUEST':'doQuery','LANG':'ADQL','QUERY':q,'MAXREC':2},timeout=(10,45))
            record.update(http_status=r.status_code,body=r.text)
        except requests.RequestException as exc: record['error']=str(exc)
        record['elapsed_seconds']=time.monotonic()-start
        records.append(record)
        (folder/'diagnosis.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**record}),flush=True)
if __name__=='__main__': main()
