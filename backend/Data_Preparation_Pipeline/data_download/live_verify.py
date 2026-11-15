import json,hashlib
from pathlib import Path
from user_input import create_request
from request_validation import validate_request
from data_download import load_catalog,download_batch,Limits

def main():
    folder=Path(__file__).resolve().parent.parent/'data/search_results/d6f57c3e-f6aa-488e-95a7-ac6f1072dd73'
    catalog=load_catalog(folder/'catalog.json');report=json.loads((folder/'report.json').read_text())
    # Original request file was not persisted in the earlier search. Reconstruct
    # its recorded geometry and retain the report's request ID, then validate.
    _,ra,dec,radius=report['queries'][0]['parameters']['POS'].split()
    request=create_request('coordinates',{'ra':float(ra),'dec':float(dec)},'sky_viewer',fov_deg=2*float(radius))
    request['request_id']=report['request_id']
    acceptance,_=validate_request(request)
    for product in catalog['products'][:2]:
        entries,manifest=download_batch(catalog,report,request,acceptance,[product['product_id']],limits=Limits(retries=0,read_timeout=90))
        print(json.dumps({'manifest':str(manifest),'entry':entries[0]},default=str),flush=True)
        if entries[0]['download_status']=='downloaded':
            saved=json.loads(manifest.read_text())['entries'][0]
            path=Path(saved['local_file_path'])
            assert path.stat().st_size==saved['file_size']
            digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
            assert digest==saved['sha256']
            break
if __name__=='__main__':main()
