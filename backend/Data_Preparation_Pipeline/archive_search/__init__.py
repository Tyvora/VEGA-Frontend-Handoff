from .search import search as tap_search, save_results, build_query, TapClient, Settings
from .sia import sia_search, SIASettings, SIAClient

def search(request, acceptance, client=None, settings=None, *, service='SIA2', collections=None):
    if service=='TAP':
        catalog,report=tap_search(request,acceptance,client,settings or Settings())
        report['service_used']='TAP'
        return catalog,report
    if service!='SIA2': raise ValueError('Unknown search service')
    return sia_search(request,acceptance,client,settings or SIASettings(),collections)
