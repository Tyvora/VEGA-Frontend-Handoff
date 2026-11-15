import io
import json
from user_input import SesameResolver, create_request

XML = b'<Sesame><Target><name>Vega</name><Resolver name="S=Simbad"><oname>Vega</oname><jradeg>279.2347</jradeg><jdedeg>38.7837</jdedeg></Resolver></Target></Sesame>'

def test_resolver_cache_refresh(monkeypatch, tmp_path):
    calls=[]
    def reply(*args, **kwargs):
        calls.append(1)
        return io.BytesIO(XML)
    monkeypatch.setattr('urllib.request.urlopen',reply)
    resolver=SesameResolver(cache_dir=tmp_path,retries=0)
    request=create_request('name','Vega','sky_viewer',resolver=resolver)
    assert request['status']=='ready_for_validation'
    resolver.resolve('Vega')
    assert len(calls)==1
    resolver.resolve('Vega',force_refresh=True)
    assert len(calls)==2
    file=next(tmp_path.glob('*.json'))
    record=json.loads(file.read_text())
    record['expires_at']=0
    file.write_text(json.dumps(record))
    resolver.resolve('Vega')
    assert len(calls)==3

