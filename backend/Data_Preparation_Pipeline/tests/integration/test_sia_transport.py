import requests
import pytest
from archive_search.sia import SIAClient,SIASettings

def test_retry_limit(monkeypatch):
    calls=[]
    def fail(*args,**kwargs):
        calls.append(1);raise requests.Timeout('offline')
    monkeypatch.setattr('requests.get',fail)
    monkeypatch.setattr('time.sleep',lambda _:None)
    with pytest.raises(requests.Timeout): SIAClient(SIASettings(retries=1)).query({})
    assert len(calls)==2

def test_byte_limit(monkeypatch):
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,*args):return iter([b'12345'])
    monkeypatch.setattr('requests.get',lambda *a,**k:Response())
    with pytest.raises(ValueError,match='byte limit'):SIAClient(SIASettings(max_bytes=4)).query({})
