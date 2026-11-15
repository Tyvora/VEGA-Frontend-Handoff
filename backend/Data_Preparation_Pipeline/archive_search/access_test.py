"""Prompt 04.2: one bounded official TAP test, SIA diagnostic only on TAP failure."""
import io,json,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from astropy.io.votable import parse
import numpy as np

QUERY="""SELECT
 'https://irsa.ipac.caltech.edu/' || a.uri || '?center=210.80227,54.34895d&size=0.1' AS uri,
 p.time_bounds_lower
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', 210.80227, 54.34895), p.poly)
 AND p.energy_bandpassname = 'SPHEREx-D2'
ORDER BY p.time_bounds_lower"""

def test_access(folder,name,url,params,timeout):
    start=time.monotonic()
    report={'test':name,'endpoint':url,'parameters':params,'started_at':datetime.now(timezone.utc).isoformat(),'status':'failed','number_of_products':None,'errors':[]}
    rows=[]
    try:
        response=requests.get(url,params=params,timeout=(10,timeout))
        report.update(http_status=response.status_code,response_url=response.url)
        (folder/(name+'.xml')).write_bytes(response.content)
        response.raise_for_status()
        document=parse(io.BytesIO(response.content))
        infos=[{'name':i.name,'value':i.value,'content':i.content} for res in document.resources for i in res.infos]
        report['infos']=infos
        errors=[i['content'] for i in infos if i['name']=='QUERY_STATUS' and i['value']=='ERROR']
        if errors: raise ValueError(str(errors))
        table=document.get_first_table().to_table(use_names_over_ids=True)
        for row in table:
            rows.append({key:None if np.ma.is_masked(row[key]) else (row[key].item() if isinstance(row[key],np.generic) else row[key]) for key in table.colnames})
        report.update(status='success',number_of_products=len(rows),completeness='limited MAXREC=2; not proof of complete retrieval',overflow=any(i['value']=='OVERFLOW' for i in infos))
        if rows:
            first=rows[0]
            link=first.get('access_url',first.get('uri'))
            report['first_product']=first
            report['access_url_is_irsa']=isinstance(link,str) and urlparse(link).scheme=='https' and urlparse(link).hostname=='irsa.ipac.caltech.edu'
    except Exception as exc: report['errors'].append(str(exc))
    report['elapsed_seconds']=time.monotonic()-start
    (folder/(name+'_catalog.json')).write_text(json.dumps(rows,indent=2,default=str),encoding='utf-8')
    (folder/(name+'_report.json')).write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps(report,default=str),flush=True)
    return report

def main():
    folder=Path(__file__).resolve().parent.parent/'data'/'search_results'/('access-'+str(uuid.uuid4()))
    folder.mkdir()
    print(str(folder),flush=True)
    tap=test_access(folder,'official_tap','https://irsa.ipac.caltech.edu/TAP/sync',{'REQUEST':'doQuery','LANG':'ADQL','QUERY':QUERY,'MAXREC':2},120)
    if tap['status']!='success':
        test_access(folder,'sia2_diagnostic','https://irsa.ipac.caltech.edu/SIA',{'COLLECTION':'spherex_dr1','POS':'CIRCLE 210.80227 54.34895 0.05','MAXREC':2},45)
if __name__=='__main__': main()

