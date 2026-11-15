"""Atomic workflow checkpoints and content-bound stage reuse."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,time,uuid

class StageFailure(ValueError):
    def __init__(self,message,outputs=(),result=None):
        super().__init__(message);self.output_references=list(outputs);self.result=result or {}

def now():return datetime.now(timezone.utc).isoformat()
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.'+str(uuid.uuid4())+'.tmp')
    with temp.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    for attempt in range(6):
        try:os.replace(temp,path);return
        except PermissionError:
            if attempt==5:raise
            time.sleep(.05*(attempt+1))
def snapshot(paths):
    result={}
    for value in paths:
        path=Path(value).resolve()
        if not path.exists():raise ValueError('Missing output reference '+str(path))
        files=[path] if path.is_file() else list(path.rglob('*'))
        for file in files:
            if file.is_file():result[str(file)]={'sha256':sha(file),'size':file.stat().st_size}
    return result

def intact(files):
    try:return bool(files) and all(Path(p).stat().st_size==s['size'] and sha(p)==s['sha256'] for p,s in files.items())
    except OSError:return False

def run_stage(workflow,manifest,stages,name,inputs,operation,verify=None):
    signature=hashlib.sha256(json.dumps(inputs,sort_keys=True,allow_nan=False).encode()).hexdigest()
    prior=stages.get(name,{})
    if prior.get('status') in ('completed','partial') and prior.get('input_signature')==signature and intact(prior.get('output_integrity',{})):
        try:
            if verify:verify(prior['result'])
            prior['reused']=True;prior['reuse_verified_at']=now();write(manifest,workflow)
            return prior['result']
        except (ValueError,OSError,KeyError):pass
    history=prior.get('history',[])+([{k:v for k,v in prior.items() if k!='history'}] if prior else [])
    stage={'status':'running','start_time':now(),'end_time':None,'input_references':inputs,'output_references':[],'errors':[],'warnings':[],'input_signature':signature,'history':history,'reused':False}
    stages[name]=stage;write(manifest,workflow)
    try:
        result,refs,status,warnings=operation()
        if verify:verify(result)
        stage.update(status=status,reused=bool(result.get('reused_from_existing',False)),end_time=now(),result=result,output_references=[str(Path(p).resolve()) for p in refs],output_integrity=snapshot(refs),warnings=warnings)
        write(manifest,workflow);return result
    except Exception as exc:
        stage.update(status='failed',end_time=now(),errors=[str(exc)],output_references=[str(p) for p in getattr(exc,'output_references',[])],result=getattr(exc,'result',{}));write(manifest,workflow);raise

def skipped(stages,names,reason):
    for name in names:
        if stages.get(name,{}).get('status') not in ('completed','partial','failed'):
            stages[name]={'status':'skipped','start_time':None,'end_time':now(),'input_references':[],'output_references':[],'errors':[],'warnings':[reason]}


