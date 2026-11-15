"""Bounded real M101 workflow verification; reuses verified existing artifacts."""
from pathlib import Path
import json
from . import run_pipeline,WorkflowLimits
ROOT=Path(__file__).resolve().parent.parent

def main():
    cached=ROOT/'data/search_results/d6f57c3e-f6aa-488e-95a7-ac6f1072dd73'
    request=ROOT/'data/requests/c7fe7b2a-55b0-48dc-bcfe-ffdc3853fb70.json'
    products=json.loads((cached/'catalog.json').read_text())['products'];chosen=[];observations=set()
    for p in products:
        if p.get('detector')=='D3' and p.get('collection')=='spherex_dr1' and p.get('observation_id') not in observations and p.get('observation_start') is not None:
            chosen.append(p);observations.add(p['observation_id'])
            if len(chosen)==3:break
    if len(chosen)!=3:raise ValueError('Three distinct documented observations unavailable')
    intervals=sorted((p['observation_start'],p['observation_end']) for p in chosen)
    if any(a[1]>=b[0] for a,b in zip(intervals,intervals[1:])):raise ValueError('Observation intervals overlap')
    workflow,path=run_pipeline([p['product_id'] for p in chosen],request_file=request,cached_search=cached,reuse_packages={chosen[0]['product_id']:str(ROOT/'data/algorithm_inputs/c40a0dfa-5780-48d5-bea2-ff235c0274c2/preparation_report.json')},limits=WorkflowLimits(max_products=3,max_network_bytes=64*1024*1024,max_seconds=300,read_timeout=90))
    print(json.dumps({'manifest':str(path),'status':workflow['status'],'summary':workflow.get('completion_summary'),'products':{pid:{'status':p['status'],'errors':p.get('errors',[]),'packages':p['package_references']} for pid,p in workflow['products'].items()}}),flush=True)
if __name__=='__main__':main()

