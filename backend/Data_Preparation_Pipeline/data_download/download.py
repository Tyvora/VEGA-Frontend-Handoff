"""Sequential, bounded IRSA FITS transport; no science validation or extraction."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Callable,Any
from urllib.parse import urlsplit,urlencode
import hashlib,json,math,os,time,uuid
import requests
from astropy.io import fits

ROOT=Path(__file__).resolve().parent.parent
@dataclass(frozen=True)
class Limits:
    connect_timeout: float=10
    read_timeout: float=60
    retries: int=1
    max_file_bytes: int=128*1024*1024
    max_total_bytes: int=256*1024*1024
    max_products: int=1
    def __post_init__(self):
        if min(self.connect_timeout,self.read_timeout,self.max_file_bytes,self.max_total_bytes,self.max_products)<=0 or not 0<=self.retries<=3: raise ValueError('Invalid download limits')

def load_catalog(path: str|Path) -> dict:
    value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if value.get('schema_version')!='1.0' or not isinstance(value.get('products'),list):raise ValueError('Unsupported catalog')
    return value

def valid_url(url: str) -> bool:
    if not isinstance(url,str): return False
    p=urlsplit(url)
    return p.scheme=='https' and p.hostname=='irsa.ipac.caltech.edu' and p.port in (None,443) and not p.username and not p.password and not p.fragment

def build_url(product: dict,request: dict,mode: str='cutout') -> tuple[str,dict|None]:
    url=product.get('access_url')
    if not valid_url(url):raise ValueError('Original IRSA HTTPS URL required')
    if mode=='full':return url,None
    if mode!='cutout':raise ValueError('Unknown mode')
    path=urlsplit(url)
    if not path.path.startswith('/ibe/data/spherex/') or not path.path.endswith('.fits') or path.query:raise ValueError('URL not a documented SPHEREx IBE FITS cutout source')
    ra,dec,fov=request['ra_deg'],request['dec_deg'],request['fov_deg']
    if request.get('coordinate_frame')!='icrs' or not all(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) for v in (ra,dec,fov)) or not 0<=ra<360 or not -90<=dec<=90 or not 0<fov<=1:raise ValueError('Invalid cutout geometry')
    params={'center':f'{ra:.12g},{dec:.12g}deg','size':f'{fov:.12g}deg','gzip':'false'}
    return url+'?'+urlencode(params),params

def inspect_fits(path: Path) -> list[str]:
    size=path.stat().st_size
    with path.open('rb') as f:
        if f.read(9)!=b'SIMPLE  =':raise ValueError('Response is not primary FITS')
    if size<2880 or size%2880:raise ValueError('Truncated FITS block')
    with fits.open(path,memmap=True,lazy_load_hdus=False) as hdus:
        hdus.verify('exception')
        for hdu in hdus:
            info=hdu.fileinfo()
            if info['datLoc']+info['datSpan']>size:raise ValueError('Truncated FITS data')
        return [hdu.name for hdu in hdus]

def download_batch(catalog: dict, report: dict, request: dict, acceptance: dict, selected_ids: list[str], *, mode: str='cutout', limits: Limits=Limits(), root: Path=ROOT, session: Any=None, cancelled: Callable[[],bool]=lambda:False) -> tuple[list[dict],Path]:
    if report.get('status') not in ('completed','partial') or report.get('request_id')!=request.get('request_id'):raise ValueError('Matching search report required')
    if acceptance.get('status')!='accepted' or acceptance.get('request_id')!=request.get('request_id') or acceptance.get('errors')!=[]:raise ValueError('Accepted request required')
    if catalog.get('schema_version')!='1.0' or not isinstance(catalog.get('products'),list):raise ValueError('Unsupported catalog')
    if not selected_ids or len(selected_ids)>limits.max_products or len(selected_ids)!=len(set(selected_ids)):raise ValueError('Explicit bounded product selection required')
    products=[]
    for identity in selected_ids:
        matches=[p for p in catalog['products'] if p.get('product_id')==identity]
        if len(matches)!=1:raise ValueError('Product identity missing or ambiguous; select an unambiguous catalog')
        products.append(matches[0])
    session=session or requests.Session(); entries=[]; total=0
    manifest_dir=Path(root)/'data'/'manifests'; manifest_dir.mkdir(parents=True,exist_ok=True)
    manifest=manifest_dir/(str(uuid.uuid4())+'.json')
    # Reserve manifest before network traffic; exclusive writes prevent overwrite.
    with manifest.open('x',encoding='utf-8') as f:json.dump({'entries':[]},f)
    for product in products:
        entry={'request_id':request['request_id'],'product_id':product.get('product_id'),'observation_id':product.get('observation_id'),'collection':product.get('collection'),'processing_version':product.get('processing_version'),'source_url':product.get('access_url'),'download_mode':mode,'cutout_parameters':None,'local_file_path':None,'file_size':None,'sha256':None,'download_timestamp':None,'download_status':'failed','error_details':None,'warnings':['Source catalog is partial'] if report['status']=='partial' else [],'source_metadata':product}
        temporary=None
        try:
            if product.get('downloadable') is not True or not product.get('product_id') or not product.get('collection'):raise ValueError('Product is not eligible')
            url,params=build_url(product,request,mode);entry.update(download_url=url,cutout_parameters=params)
            folder=Path(root)/'data'/('cutouts' if mode=='cutout' else 'raw');folder.mkdir(parents=True,exist_ok=True)
            final=folder/(str(uuid.uuid4())+'.fits');temporary=final.with_suffix('.part')
            for attempt in range(limits.retries+1):
                try:
                    if cancelled():raise InterruptedError('Cancelled')
                    digest=hashlib.sha256();size=0
                    with session.get(url,stream=True,timeout=(limits.connect_timeout,limits.read_timeout),allow_redirects=False,headers={'Accept-Encoding':'identity'}) as response:
                        entry['http_status']=response.status_code
                        response.raise_for_status()
                        if response.status_code!=200:raise ValueError('Unexpected HTTP status or redirect')
                        if 'html' in response.headers.get('Content-Type','').lower():raise ValueError('HTML response')
                        length=response.headers.get('Content-Length')
                        if length and int(length)>min(limits.max_file_bytes,limits.max_total_bytes-total):raise ValueError('Declared download size exceeds limit')
                        with temporary.open('xb') as stream:
                            for chunk in response.iter_content(65536):
                                if cancelled():raise InterruptedError('Cancelled')
                                size+=len(chunk);total+=len(chunk)
                                if size>limits.max_file_bytes or total>limits.max_total_bytes:raise ValueError('Download byte budget exceeded')
                                stream.write(chunk);digest.update(chunk)
                            stream.flush();os.fsync(stream.fileno())
                        if length and size!=int(length):raise ValueError('Incomplete HTTP body')
                    published=product.get('raw',{})
                    if mode=='full':
                        if published.get('contentlength') is not None and size!=int(published['contentlength']):raise ValueError('Published size mismatch')
                        checksum=published.get('contentchecksum')
                        if isinstance(checksum,str) and checksum.startswith('sha256:') and digest.hexdigest()!=checksum[7:]:raise ValueError('Published checksum mismatch')
                    extensions=inspect_fits(temporary)
                    # Hard-link publication is atomic and fails if destination exists.
                    os.link(temporary,final);temporary.unlink();temporary=None
                    entry.update(local_file_path=str(final.resolve()),file_size=size,sha256=digest.hexdigest(),extensions=extensions,download_status='downloaded',download_timestamp=datetime.now(timezone.utc).isoformat())
                    break
                except requests.HTTPError as exc:
                    if temporary.exists():temporary.unlink()
                    if response.status_code not in (408,429) and response.status_code<500:raise
                    if attempt==limits.retries:raise
                    time.sleep(.5*2**attempt)
                except (requests.ConnectionError,requests.Timeout,requests.exceptions.ChunkedEncodingError):
                    if temporary.exists():temporary.unlink()
                    if attempt==limits.retries:raise
                    time.sleep(.5*2**attempt)
            # access_estsize is approximate kbyte and not a trusted size/checksum.
            entry['published_integrity_comparison']='No exact published size/checksum in current catalog; HTTP Content-Length checked when present'
        except Exception as exc:entry['error_details']=str(exc)
        finally:
            if temporary is not None and temporary.exists():temporary.unlink()
        entries.append(entry)
        stage=manifest.with_suffix('.tmp')
        with stage.open('x',encoding='utf-8') as f:json.dump({'schema_version':'1.0','request_id':request['request_id'],'network_bytes':total,'request_snapshot':request,'acceptance_snapshot':acceptance,'search_report_snapshot':report,'entries':entries},f,indent=2,allow_nan=False)
        for save_attempt in range(5):
            try:
                os.replace(stage,manifest)
                break
            except PermissionError:
                if save_attempt==4:raise
                time.sleep(.05*(save_attempt+1))
    return entries,manifest



