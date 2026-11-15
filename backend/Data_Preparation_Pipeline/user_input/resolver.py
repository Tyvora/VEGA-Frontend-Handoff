from __future__ import annotations
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINTS = ('https://cds.unistra.fr/cgi-bin/nph-sesame/-ox/~SNV?', 'https://vizier.idia.ac.za/viz-bin/nph-sesame/-ox/~SNV?')
MOVING = {'sun','moon','mercury','venus','earth','mars','jupiter','saturn','uranus','neptune','pluto'}
DEFAULT_CACHE = Path(__file__).resolve().parent / 'cache'

def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat()

class SesameResolver:
    def __init__(self, cache_dir: str | Path | None = None, timeout: float = 5, retries: int = 1, endpoint: int = 0):
        if endpoint not in (0,1) or timeout <= 0 or not 0 <= retries <= 3: raise ValueError('Invalid resolver configuration')
        self.endpoint, self.timeout, self.retries = ENDPOINTS[endpoint], timeout, retries
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE

    def resolve(self, name: str, force_refresh: bool = False) -> dict[str, Any]:
        if not isinstance(name,str) or not name.strip() or len(name)>120 or not re.fullmatch(r"[\w\s+.*'()\-]+",name, re.UNICODE):
            return {'resolution_status':'invalid_input'}
        clean=' '.join(name.split())
        if clean.casefold() in MOVING: return {'resolution_status':'unsupported_target', 'warnings':['Solar system targets move with time.']}
        key=hashlib.sha256((self.endpoint+'|v2|'+clean.casefold()).encode()).hexdigest()
        path=self.cache_dir/(key+'.json')
        now=time.time()
        if not force_refresh:
            try:
                record=json.loads(path.read_text(encoding='utf-8'))
                if record['expires_at'] > now and record['result']['resolution_status'] in ('resolved','not_found','ambiguous'):
                    return record['result']
            except (OSError, ValueError, KeyError, TypeError): pass
        result={'resolution_status':'service_unavailable'}
        for attempt in range(self.retries+1):
            try:
                url=self.endpoint+urllib.parse.quote(clean, safe='')
                with urllib.request.urlopen(url,timeout=self.timeout) as response:
                    raw=response.read(1024*1024+1)
                if len(raw)>1024*1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise ValueError('Invalid response')
                root=ET.fromstring(raw)
                targets=root.findall('Target')
                if root.tag != 'Sesame' or len(targets)!=1: raise ValueError('Invalid Sesame response')
                target=targets[0]
                if ' '.join((target.findtext('name') or '').split()).casefold()!=clean.casefold(): raise ValueError('Target identity mismatch')
                candidates=[]
                for item in target.findall('Resolver'):
                    ra, dec=item.findtext('jradeg'),item.findtext('jdedeg')
                    canonical=(item.findtext('oname') or '').strip()
                    source=(item.get('name') or '').strip()
                    if ra is None or dec is None or not canonical or not source: raise ValueError('Incomplete resolver result')
                    ra,dec=float(ra),float(dec)
                    if not math.isfinite(ra) or not math.isfinite(dec) or not 0<=ra<360 or not -90<=dec<=90: raise ValueError('Invalid position')
                    candidates.append({'canonical_name':canonical, 'ra_deg':ra, 'dec_deg':dec, 'resolver_source':source, 'coordinate_reference':item.findtext('refPos'), 'identifier':item.findtext('oid')})
                if len(candidates)>1:
                    result={'resolution_status':'ambiguous','candidates':candidates}
                elif candidates:
                    candidate=candidates[0]
                    candidate.pop('identifier')
                    result={'resolution_status':'resolved',**candidate}
                elif any(re.fullmatch(r'\*+\s*NNNothing found\s*\*+', (info.text or '').strip(), re.I) for info in target.findall('INFO')):
                    result={'resolution_status':'not_found'}
                else: raise ValueError('Incomplete or unrecognized response')
                result['resolver_endpoint']=self.endpoint.split('?')[0]
                result['retrieved_at']=_stamp(time.time())
                break
            except urllib.error.HTTPError as exc:
                result={'resolution_status': 'service_unavailable' if exc.code in (408,429) or exc.code>=500 else 'resolver_error'}
                if result['resolution_status']=='resolver_error': break
                if attempt<self.retries: time.sleep(0.25*(2**attempt))
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt<self.retries: time.sleep(0.25*(2**attempt))
            except (ValueError, ET.ParseError):
                result={'resolution_status':'resolver_error'}
                break
        ttl={'resolved':604800,'not_found':3600,'ambiguous':3600}.get(result['resolution_status'])
        if ttl:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                record={'original_name':name,'source':self.endpoint,'cached_at':now,'expires_at':now+ttl,'result':result}
                temporary=path.with_name(path.name+'.'+hashlib.sha256(str(time.time_ns()).encode()).hexdigest()+'.tmp')
                with temporary.open('x', encoding='utf-8') as f: json.dump(record,f)
                temporary.replace(path)
            except OSError:
                pass
        return result
