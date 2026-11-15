import json,time,uuid
from pathlib import Path
from archive_search.search import TapClient,save_results
from archive_search.catalog import normalize

def main():
    query="SELECT TOP 2 a.artifactid,a.uri,p.productid,p.energy_bandpassname,p.time_bounds_lower FROM spherex.artifact a JOIN spherex.plane p ON a.planeid=p.planeid WHERE 1=CONTAINS(POINT('ICRS',279.234734787,38.783688956),p.poly) AND p.energy_bandpassname='SPHEREx-D2'"
    report={'request_id':None,'query':query,'mode':'async','status':'failed','errors':[],'warnings':['Center-only diagnostic; not full circle overlap'],'number_of_results':0}
    rows=[]; start=time.monotonic()
    try:
        rows,status=TapClient(async_mode=True,job_timeout=45).query(query,2)
        report.update(status='partial' if rows else 'no_results',tap_status=status,number_of_results=len(rows))
    except Exception as exc: report['errors'].append(str(exc))
    products,warnings=normalize(rows)
    report['warnings']+=warnings; report['elapsed_seconds']=time.monotonic()-start
    folder=save_results({'products':products,'raw_rows':rows},report)
    print(json.dumps({'folder':str(folder),'report':report}),flush=True)
if __name__=='__main__': main()
