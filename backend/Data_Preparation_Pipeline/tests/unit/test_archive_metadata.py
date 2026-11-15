import pytest
from archive_search.catalog import normalize
from archive_search.retrieval import retrieve_batches

def test_identity_versions_detectors():
    rows=[{'artifactid':'a','productid':'same','energy_bandpassname':'SPHEREx-D1','provenance_version':'1'}, {'artifactid':'b','productid':'same','energy_bandpassname':'SPHEREx-D2','provenance_version':'2'}]
    products,warnings=normalize(rows+[rows[0]])
    assert len(products)==2 and products[0]['detector']=='D1' and products[1]['processing_version']=='2'
    assert all(p['data_release'] is None for p in products)

def test_missing_and_invalid_url():
    products,warnings=normalize([{}, {'artifactid':'a','uri':'https://evil.example/file.fits'}])
    assert warnings and products[0]['access_url'] is None

@pytest.mark.parametrize('uri', ['/data/SPHEREx/file.fits','https://irsa.ipac.caltech.edu/data/file.fits'])
def test_access_urls(uri):
    products,_=normalize([{'artifactid':'a','uri':uri}])
    assert products[0]['access_url'].startswith('https://irsa.ipac.caltech.edu/')

def test_batch_overlap():
    pages=iter([([{'artifactid':'a'},{'artifactid':'b'}],True),([{'artifactid':'b'},{'artifactid':'c'}],False)])
    rows,complete,reason=retrieve_batches(lambda cursor:next(pages))
    assert complete and [r['artifactid'] for r in rows]==['a','b','c']

def test_missing_page():
    def fail(cursor):
        if cursor: raise TimeoutError('offline')
        return [{'artifactid':'a'}],True
    rows,complete,reason=retrieve_batches(fail)
    assert len(rows)==1 and not complete and reason=='offline'

def test_page_limit():
    rows,complete,_=retrieve_batches(lambda cursor:([{'artifactid':'a'}],True),1)
    assert rows and not complete
