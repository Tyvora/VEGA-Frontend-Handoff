from __future__ import annotations
import json
import math
import uuid
from pathlib import Path
from typing import Any
from astropy.coordinates import SkyCoord
from astropy import units as u

# J2000 catalog position; angular diameter is an application default.
PRESETS = {"m31": {"preset_id": "m31", "name": "M31", "ra_deg": 10.6847083, "dec_deg": 41.26875, "coordinate_frame": "icrs", "default_fov_deg": 0.1, "description": "Andromeda galaxy center", "source_reference": "https://ned.ipac.caltech.edu/byname?objname=M31", "version": "1"}}

def create_request(method: str, value: Any, goal: str, fov_deg: float | None = None, resolver: Any = None, force_refresh: bool = False) -> dict[str, Any]:
    if goal not in {"sky_viewer", "timeline", "discoveries"}: raise ValueError("Invalid exploration goal")
    result = {"schema_version": "1.0", "request_id": str(uuid.uuid4()), "input_method": method, "original_input": value, "target_name": None, "canonical_name": None, "ra_deg": None, "dec_deg": None, "coordinate_frame": "icrs", "coordinate_reference": None, "resolver_source": None, "resolution_status": None, "region_shape": "circle", "fov_deg": None, "fov_source": "default", "goal": goal, "status": "needs_resolution", "warnings": []}
    preset = None
    if method == "coordinates":
        if not isinstance(value, dict) or set(value) != {"ra", "dec"}: raise ValueError("Coordinates require ra and dec")
        ra, dec = value["ra"], value["dec"]
        if isinstance(ra, bool) or isinstance(dec, bool): raise ValueError("Invalid coordinates")
        if isinstance(ra, (int, float)) and isinstance(dec, (int, float)):
            if not math.isfinite(ra) or not math.isfinite(dec) or not 0 <= ra < 360: raise ValueError("Invalid RA")
            coord = SkyCoord(ra=ra*u.deg, dec=dec*u.deg, frame="icrs")
        elif isinstance(ra, str) and isinstance(dec, str) and 'h' in ra.lower() and ('d' in dec.lower() or '°' in dec):
            coord = SkyCoord(ra=ra, dec=dec.replace('°','d').replace('′','m').replace('″','s'), frame="icrs")
        else: raise ValueError("Ambiguous coordinate units")
        result.update(ra_deg=float(coord.ra.deg), dec_deg=float(coord.dec.deg), coordinate_reference="user supplied ICRS", status="ready_for_validation")
    elif method == "preset":
        if not isinstance(value,str) or value not in PRESETS: raise ValueError("Unknown preset")
        preset = PRESETS[value]
        result.update(ra_deg=preset['ra_deg'], dec_deg=preset['dec_deg'], coordinate_reference=preset['source_reference'], preset_id=value, preset_version=preset['version'], status="ready_for_validation")
    elif method == "name":
        if not isinstance(value, str): raise ValueError("Name must be a string")
        if resolver is None:
            from .resolver import SesameResolver
            resolver = SesameResolver()
        result.update(resolver.resolve(value, force_refresh=force_refresh))
        result['target_name'] = value
        if result['resolution_status'] == 'resolved': result['status'] = 'ready_for_validation'
    else: raise ValueError("Unknown input method")
    if fov_deg is not None:
        if isinstance(fov_deg,bool) or not isinstance(fov_deg,(int,float)) or not math.isfinite(fov_deg) or fov_deg <= 0: raise ValueError("Invalid FOV diameter")
        result.update(fov_deg=float(fov_deg), fov_source='user')
    elif preset: result.update(fov_deg=preset['default_fov_deg'], fov_source='preset')
    else: result['fov_deg']=0.1
    return result

def save_request(request: dict[str, Any], directory: str | Path) -> Path:
    path=Path(directory)/(str(uuid.UUID(request['request_id']))+'.json')
    with path.open('x', encoding='utf-8') as stream: json.dump(request, stream, ensure_ascii=False, allow_nan=False, indent=2)
    return path

