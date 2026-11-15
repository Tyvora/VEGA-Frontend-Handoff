from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import uuid
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / 'contracts' / 'input_contract.json').read_text(encoding='utf-8-sig'))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

@dataclass(frozen=True)
class ValidationSettings:
    min_fov_deg: float = 0.001
    max_fov_deg: float = 1.0
    def __post_init__(self):
        if not (math.isfinite(self.min_fov_deg) and math.isfinite(self.max_fov_deg) and 0 < self.min_fov_deg <= self.max_fov_deg):
            raise ValueError('Invalid FOV limits')

def validate_request(request, settings=ValidationSettings()):
    errors = []
    for error in VALIDATOR.iter_errors(request):
        path = '/' + '/'.join(str(x).replace('~','~0').replace('/','~1') for x in error.absolute_path)
        errors.append({'path': path, 'message': error.message})
    if isinstance(request, dict):
        for field, low, high, inclusive in [('ra_deg',0,360,False),('dec_deg',-90,90,True),('fov_deg',settings.min_fov_deg,settings.max_fov_deg,True)]:
            value=request.get(field)
            valid = not isinstance(value,bool) and isinstance(value,(float,int)) and math.isfinite(value) and low <= value and (value <= high if inclusive else value < high)
            if not valid: errors.append({'path':'/'+field,'message':f'Must be finite and within {low} to {high}' + (' inclusive' if inclusive else ', upper bound exclusive')})
        if request.get('status') != 'ready_for_validation': errors.append({'path':'/status','message':'Request is not ready for archive search'})
        if request.get('input_method') == 'name' and request.get('resolution_status') != 'resolved': errors.append({'path':'/resolution_status','message':'Name must be resolved'})
        if request.get('input_method') == 'name' and request.get('target_name') != request.get('original_input'): errors.append({'path':'/target_name','message':'Target must match original name'})
        if request.get('input_method') == 'preset' and request.get('preset_id') != request.get('original_input'): errors.append({'path':'/preset_id','message':'Preset must match original input'})
    report={'request_id':request.get('request_id') if isinstance(request,dict) else None,'status':'rejected' if errors else 'accepted','errors':errors,'warnings':[], 'validated_at':datetime.now(timezone.utc).isoformat(), 'schema_version':'1.0'}
    return report, request if not errors else None

def save_report(report, directory=ROOT/'data'/'validation'):
    path=Path(directory)/(str(uuid.uuid4())+'.json')
    with path.open('x', encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,allow_nan=False,indent=2)
    return path
