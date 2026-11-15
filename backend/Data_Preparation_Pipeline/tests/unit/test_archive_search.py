import pytest
from user_input import create_request
from request_validation import validate_request
from archive_search import search, build_query, save_results

def test_query_and_acceptance(tmp_path):
    r=create_request('coordinates',{'ra':359.99,'dec':89},'sky_viewer')
    acceptance,_=validate_request(r)
    assert 'INTERSECTS' in build_query(r) and '0.05' in build_query(r)
    class Client:
        def query(self,*args): return [{'artifactid':'mock-only'}],'OVERFLOW'
    catalog,report=search(r,acceptance,Client(),service='TAP')
    assert report['status']=='partial' and report['completeness']['overflow']
    assert catalog['products'][0]['downloadable'] is False
    path=save_results(catalog,report,tmp_path)
    assert (path/'report.json').exists()
    with pytest.raises(ValueError): search(r,{'status':'rejected'})


