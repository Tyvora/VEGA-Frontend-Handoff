"""Offline acceptance tests for presentation contracts; no science/API execution."""
import copy
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2] / 'frontend_contracts'
VIEWS = ('sky_viewer', 'timeline', 'discoveries')
SCHEMAS = sorted(ROOT.rglob('*.schema.json'))
MOCKS = sorted(ROOT.rglob('*.mock.json'))


def reject_constant(value):
    raise ValueError('Non-finite JSON token: ' + value)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=reject_constant)


DOCUMENTS = {load(p)['$id']: load(p) for p in SCHEMAS}
REGISTRY = Registry().with_resources((key, Resource.from_contents(s)) for key, s in DOCUMENTS.items())
COMMON = load(ROOT / 'shared/common.schema.json')


def validator(view):
    return Draft202012Validator(load(ROOT / view / 'response.schema.json'), registry=REGISTRY,
                                 format_checker=FormatChecker())


def definition(name):
    return Draft202012Validator({'$ref': COMMON['$id'] + '#/$defs/' + name},
                                registry=REGISTRY, format_checker=FormatChecker())


def fixture(view):
    return load(ROOT / view / 'example.mock.json')


def walk(value):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def assign(payload, path, value):
    cursor = payload
    for name in path[:-1]:
        cursor = cursor[name]
    cursor[path[-1]] = value


@pytest.mark.parametrize('path', SCHEMAS, ids=lambda p: str(p.relative_to(ROOT)))
def test_valid_schema_and_all_refs_resolve_offline(path):
    schema = load(path)
    Draft202012Validator.check_schema(schema)
    assert schema['$schema'] == 'https://json-schema.org/draft/2020-12/schema'
    for item in walk(schema):
        if isinstance(item, dict) and '$ref' in item:
            absolute = urljoin(schema['$id'], item['$ref'])
            assert REGISTRY.resolver().lookup(absolute).contents is not None


@pytest.mark.parametrize('path', MOCKS, ids=lambda p: str(p.relative_to(ROOT)))
def test_all_mock_payloads_match_schema(path):
    validator(path.parent.name).validate(load(path))


@pytest.mark.parametrize('path', MOCKS, ids=lambda p: str(p.relative_to(ROOT)))
def test_fixture_identity_joins_assets_and_mock_labels(path):
    payload = load(path)
    assert payload['is_mock'] and payload['provenance']['synthetic']
    assert payload['data_origin'] == 'mock'
    assert payload['state']['scientific_validation'] != 'validated'
    assert any(w['code'] == 'MOCK_NOT_SCIENCE' for w in payload['warnings'])
    for item in walk(payload):
        if not isinstance(item, dict):
            continue
        if 'asset_id' in item:
            assert item['availability'] == 'fixture'
            url = urlparse(item['href'])
            assert not url.scheme and not url.netloc
            target = (path.parent / unquote(url.path)).resolve()
            assert target.is_relative_to(ROOT)
            assert target.is_file()
            assert 'MOCK' in target.read_text(encoding='utf-8')
        if 'is_mock' in item:
            assert item['is_mock'] is True
    data = payload['data']
    if 'observations' in data:
        rows = data['observations']
        ids = {row['product_id'] for row in rows}
        assert len(ids) == len(rows)
        if path.parent.name == 'sky_viewer':
            selected = data['selected_product_id']
            assert selected is None or selected in ids
            assert ('image' in data['available_layers']) == (data['image'] is not None)
        else:
            assert set(data['selected_product_ids']) <= ids
            for group in data['compatibility_groups']:
                assert set(group['product_ids']) <= ids
            assert data['page']['returned'] == len(rows)
    else:
        assert data['page']['returned'] == len(data['candidates'])
        for candidate in data['candidates']:
            assert {e['observation_id'] for e in candidate['evidence']} <= set(candidate['supporting_observation_ids'])
            assert candidate['candidate_type'] in data['available_candidate_types']


BAD_COMMON = [
    (['schema_version'], '2.0.0'),
    (['state', 'scientific_validation'], 'validated'),
    (['provenance', 'synthetic'], False),
    (['data_origin'], 'science_result'),
    (['state', 'data_readiness', 'allow_scientific_execution'], True),
    (['target', 'position', 'ra_deg'], 360),
    (['target', 'position', 'dec_deg'], -90.001),
    (['target', 'position', 'frame'], 'FK5'),
    (['state', 'ui_availability'], 'ready'),
    (['features', 'pixel_readout', 'allow_interaction'], True),
]


@pytest.mark.parametrize('view', VIEWS)
@pytest.mark.parametrize('path,value', BAD_COMMON, ids=[str(x[0]) for x in BAD_COMMON])
def test_reject_invalid_shared_scientific_states(view, path, value):
    payload = fixture(view)
    assign(payload, path, value)
    assert list(validator(view).iter_errors(payload))


@pytest.mark.parametrize('view', VIEWS)
@pytest.mark.parametrize('field', ['request_id', 'schema_version', 'state', 'provenance'])
def test_required_root_fields(view, field):
    payload = fixture(view)
    del payload[field]
    assert not validator(view).is_valid(payload)


@pytest.mark.parametrize('view', VIEWS)
def test_unknown_root_fields_and_impossible_ui_states(view):
    payload = fixture(view)
    payload['confidence_score'] = 0.99
    assert not validator(view).is_valid(payload)
    del payload['confidence_score']
    payload['state']['ui_availability'] = 'error'
    assert not validator(view).is_valid(payload)
    payload['state']['ui_availability'] = 'loading'
    assert not validator(view).is_valid(payload)


@pytest.mark.parametrize('path,value', [
    (['data','image','unit'], 'Jy'),
    (['data','image','wcs','frame'], 'galactic'),
    (['data','image','science_shape'], [0, 64]),
    (['data','image','display_only'], False),
    (['data','source_overlay','availability'], 'available'),
])
def test_reject_invalid_sky_measurement_and_overlay(path, value):
    payload = fixture('sky_viewer')
    assign(payload,path,value)
    assert not validator('sky_viewer').is_valid(payload)


@pytest.mark.parametrize('eligibility_field', ['scientific_comparison','difference'])
def test_native_unaligned_timeline_cannot_be_scientific(eligibility_field):
    payload = fixture('timeline')
    payload['data']['compatibility_groups'][0]['eligibility'][eligibility_field] = True
    assert not validator('timeline').is_valid(payload)


def test_difference_requires_real_asset_and_execution_permission():
    payload = fixture('timeline')
    group = payload['data']['compatibility_groups'][0]
    group.update(bandpass_status='verified_compatible', alignment_status='registered_verified',
                 calibration_status='verified')
    group['eligibility'].update(mode='scientific',scientific_comparison=True,difference=True)
    assert not validator('timeline').is_valid(payload)
    group['difference_asset'] = payload['data']['observations'][0]['preview']
    assert not validator('timeline').is_valid(payload)  # readiness/execution still insufficient


@pytest.mark.parametrize('path,value', [
    (['data','candidates',0,'confidence_score'], 0.999),
    (['data','candidates',0,'validation_status'], 'confirmed'),
    (['data','candidates',0,'is_mock'], False),
    (['data','candidates',0,'evidence',0,'is_mock'], False),
    (['data','candidates',0,'supporting_observation_ids'], []),
    (['data','candidates',0,'evidence'], []),
])
def test_candidate_evidence_cannot_be_fabricated_as_validated(path,value):
    payload = fixture('discoveries')
    assign(payload,path,value)
    assert not validator('discoveries').is_valid(payload)


def test_nonmock_candidate_needs_execution_reference_and_authorized_science():
    payload = fixture('discoveries')
    payload.update(is_mock=False,data_origin='science_result')
    payload['provenance']['synthetic'] = False
    candidate = payload['data']['candidates'][0]
    candidate['is_mock'] = False
    candidate['evidence'][0]['is_mock'] = False
    assert not validator('discoveries').is_valid(payload)
    payload['state']['data_readiness'].update(status='ready', allow_scientific_execution=True)
    payload['state']['algorithm_execution'] = 'completed'
    assert not validator('discoveries').is_valid(payload)
    payload['data']['execution_reference'] = 'authorized-test-execution'
    assert not validator('discoveries').is_valid(payload)  # fixture asset cannot be made real by relabeling
    candidate['evidence'][0]['asset'].update(availability='published',sha256='0'*64,href='https://example.invalid/test-only.png')
    validator('discoveries').validate(payload)  # structural example only, no science execution


def test_validated_requires_actual_validation_reference():
    payload = fixture('sky_viewer')
    payload.update(is_mock=False,data_origin='science_result')
    payload['provenance'].update(synthetic=False, references=['test-source-reference'])
    payload['data']['observations'][0]['is_mock'] = False
    payload['state'].update(algorithm_execution='completed',scientific_validation='validated')
    payload['state']['data_readiness'].update(status='ready',allow_scientific_execution=True)
    assert not validator('sky_viewer').is_valid(payload)
    payload['provenance']['validation_reference'] = 'test-independent-validation'
    assert not validator('sky_viewer').is_valid(payload)  # published/hash-backed asset is still absent
    payload['data']['image']['asset'].update(availability='published',sha256='0'*64,href='https://example.invalid/test-only.png')
    payload['data']['observations'][0]['preview'].update(availability='published',sha256='0'*64,href='https://example.invalid/test-only.png')
    validator('sky_viewer').validate(payload)  # schema acceptance is not authenticity verification


@pytest.mark.parametrize('unit', ['MJy/sr','(MJy/sr)^2','Jy','arcsec','mas/yr'])
def test_measurement_units_and_uncertainty(unit):
    m = dict(name='test-only',value=1,unit=unit,uncertainty_status='reported',uncertainty=0.1,
             method='test',method_version='1')
    definition('Measurement').validate(m)
    m['uncertainty'] = None
    assert not definition('Measurement').is_valid(m)
    m.update(uncertainty_status='not_reported',uncertainty=None,value=None)
    definition('Measurement').validate(m)


@pytest.mark.parametrize('token', ['NaN', 'Infinity', '-Infinity'])
def test_nonfinite_json_is_rejected_before_schema(token):
    with pytest.raises(ValueError):
        json.loads('{"value":'+token+'}', parse_constant=reject_constant)


@pytest.mark.parametrize('ra,dec', [(0,-90),(359.999999,90)])
def test_celestial_position_boundaries(ra,dec):
    definition('Position').validate(dict(ra_deg=ra,dec_deg=dec,frame='ICRS'))


def test_native_raster_centers_map_to_zero_based_science_pixels():
    image = fixture('sky_viewer')['data']['image']
    affine = image['raster_edge_to_science_pixel_affine']
    def apply(u,v):
        return tuple(row[0]*u+row[1]*v+row[2] for row in affine)
    assert apply(.5,.5) == (0,63)
    assert apply(63.5,63.5) == (63,0)
    assert image['raster_dimensions'] == {'width':64,'height':64}
    assert 'MOCK' in (ROOT/'shared/mock_preview.svg').read_text()


def test_run_payload_requires_saved_request_search_explicit_selection():
    run = dict(request_id='saved-request',search_id='saved-search',selected_product_ids=['product-1'],
               idempotency_key='test-key')
    definition('StartRun').validate(run)
    for ids in [[], ['p','p'], ['p1','p2','p3','p4']]:
        bad = dict(run,selected_product_ids=ids)
        assert not definition('StartRun').is_valid(bad)
    for key in ['request_id','search_id']:
        bad = dict(run)
        del bad[key]
        assert not definition('StartRun').is_valid(bad)
    assert not definition('StartRun').is_valid(dict(run,target_input={'input_method':'name','value':'Vega'}))


@pytest.mark.parametrize('method,value', [('name','Vega'),('preset','m31'),
    ('coordinates',{'ra':279.2347,'dec':38.7837}),
    ('coordinates',{'ra':'18h36m56.3s','dec':'+38d47m01s'})])
def test_proposed_target_payload_matches_user_input_shape(method,value):
    definition('TargetInput').validate(dict(input_method=method,value=value,goal='sky_viewer',fov_deg=.1))


def test_api_error_structure():
    error=dict(request_id=None,run_id=None,errors=[dict(code='TEST',message='Test failure',
        severity='error',scope='target',retryable=True)],warnings=[])
    definition('ApiError').validate(error)
    error['errors']=[]
    assert not definition('ApiError').is_valid(error)


@pytest.mark.parametrize('path', sorted(ROOT.rglob('*.md')), ids=lambda p:str(p.relative_to(ROOT)))
def test_document_local_links_exist(path):
    for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        url = urlparse(link)
        if url.scheme or link.startswith('#'):
            continue
        assert (path.parent / unquote(url.path)).is_file(), (path,link)


def test_deliverable_inventory_and_six_states_each():
    for name in ['FRONTEND_HANDOFF.md','RESEARCH_REPORT.md','DESIGN_DECISIONS.md',
                 'shared/states.md','shared/API_PROPOSAL.md','shared/TRACEABILITY.md']:
        assert (ROOT/name).stat().st_size > 500
    assert len(SCHEMAS)==4
    assert len(MOCKS)==18
    expected={'example','loading','partial','empty','unavailable','error'}
    for view in VIEWS:
        assert {f.name.split('.')[0] for f in (ROOT/view).glob('*.mock.json')}==expected


@pytest.mark.parametrize('view', VIEWS)
def test_empty_state_cannot_contain_results(view):
    payload = fixture(view)
    payload['state']['ui_availability'] = 'empty'
    assert not validator(view).is_valid(payload)


@pytest.mark.parametrize('algorithm,product_type', [
    ('background_estimation','background_model'),('source_detection','source_catalog'),
    ('astrometry','astrometric_solution'),('photometry','photometry_table'),
    ('observation_compatibility','compatibility_assessment'),('image_registration','registered_image'),
    ('cross_matching','crossmatch_table'),('change_detection','difference_image'),
    ('motion_detection','motion_track'),('candidate_assessment','candidate_assessment')])
def test_all_ten_scientific_product_mappings(algorithm,product_type):
    provenance=fixture('sky_viewer')['provenance']
    result=dict(result_id='mock-result',algorithm=algorithm,product_type=product_type,
        method='mock-only',method_version='1',product_ids=['mock-product-1'],
        observation_ids=['mock-observation-1'],asset=None,measurements=[],positions=[],
        related_ids=[],uncertainty_status='not_reported',validation_status='unvalidated',
        is_mock=True,provenance=provenance)
    definition('ScientificProduct').validate(result)
    result['product_type']='candidate_assessment' if product_type!='candidate_assessment' else 'background_model'
    assert not definition('ScientificProduct').is_valid(result)
    result['product_type']=product_type
    result['validation_status']='validated'
    assert not definition('ScientificProduct').is_valid(result)
