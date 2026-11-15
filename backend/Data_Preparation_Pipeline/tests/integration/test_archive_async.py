import pytest
from archive_search.search import TapClient

class Result:
    fieldnames=['artifactid']
    query_status='OK'
    def __iter__(self): return iter([{'artifactid':'test-only'}])

@pytest.mark.parametrize('phase',['COMPLETED','ERROR'])
def test_async_job_lifecycle(monkeypatch,phase):
    class Job:
        deleted=False
        def run(self): pass
        def wait(self,**kwargs): pass
        def abort(self): pass
        def raise_if_error(self): pass
        def fetch_result(self): return Result()
        def delete(self): self.deleted=True
    job=Job(); job.phase=phase
    class Service:
        def submit_job(self,*args,**kwargs): return job
    client=TapClient(async_mode=True)
    client.service=Service()
    if phase=='ERROR':
        with pytest.raises(RuntimeError): client.query('mock',2)
    else:
        assert client.query('mock',2)[0][0]['artifactid']=='test-only'
    assert job.deleted
