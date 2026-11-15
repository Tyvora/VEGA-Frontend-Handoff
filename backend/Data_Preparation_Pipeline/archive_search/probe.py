import pyvo,json
from pathlib import Path
s=pyvo.dal.TAPService('https://irsa.ipac.caltech.edu/TAP')
q="SELECT TOP 2 a.artifactid,a.uri,a.producttype,a.contenttype,p.productid,p.calibrationlevel,p.obsid,p.energy_bandpassname,p.provenance_version,o.collection,o.observationid FROM spherex.artifact a JOIN spherex.plane p ON a.planeid=p.planeid JOIN spherex.observation o ON p.obsid=o.obsid WHERE 1=CONTAINS(POINT('ICRS',210.80227,54.34895),p.poly)"
try:
 r=s.search(q,maxrec=2)
 result={'query':q,'rows':[{n:str(row[n]) for n in r.fieldnames} for row in r],'status':r.query_status}
except Exception as e: result={'query':q,'error':str(e)}
print(json.dumps(result,indent=2))
Path(__file__).with_name('live_probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')

