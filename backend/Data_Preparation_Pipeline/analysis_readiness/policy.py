"""Versioned operational readiness decisions, without algorithm execution."""
from dataclasses import dataclass,asdict
import math
VERSION='vega-readiness-1.0'
CAPABILITIES=('sky_visualization','source_detection','background_estimation','photometry','temporal_comparison','spectral_analysis')
@dataclass(frozen=True)
class Policy:
    min_analysis_fraction:float=.1
    min_background_pixels:int=32
    min_background_fraction:float=.01
    min_background_occupied_fraction:float=.5
    grid_size:int=4
    def __post_init__(self):
        if not all(math.isfinite(v) and 0<=v<=1 for v in (self.min_analysis_fraction,self.min_background_fraction,self.min_background_occupied_fraction)) or self.min_background_pixels<1 or not 1<=self.grid_size<=16:raise ValueError('Invalid operational policy')

def decision(status,codes,evidence,missing=(),steps=(),warnings=()):
    return {'status':status,'reason_codes':list(codes),'evidence':evidence,'missing_requirements':list(missing),'warnings':list(warnings),'required_next_steps':list(steps),'policy_version':VERSION,'allow_preparation':status!='blocked','allow_scientific_execution':status=='ready','execution_conditions':list(missing)+list(steps) if status!='ready' else ['Use only the specified capability; readiness does not validate scientific results']}

def temporal(records):
    reasons=[]
    independent={r.get('observation_id') for r in records if r.get('observation_id')}
    if len(independent)<2:reasons.append('SECOND_INDEPENDENT_OBSERVATION_MISSING')
    if any(r.get('observation_time') is None for r in records):reasons.append('OBSERVATION_TIME_MISSING')
    times={r.get('observation_time') for r in records if r.get('observation_time') is not None}
    if len(records)>1 and len(times)<2:reasons.append('INDEPENDENT_TIMES_UNPROVEN')
    bands={r.get('bandpass') for r in records}
    if None in bands:reasons.append('BANDPASS_MISSING')
    elif len(bands)>1:reasons.append('BANDPASSES_INCOMPATIBLE')
    if any(not r.get('wcs') for r in records):reasons.append('SPATIAL_WCS_MISSING')
    return decision('blocked' if reasons else 'conditional',reasons or ['TEMPORAL_CALIBRATION_UNVERIFIED'],{'prepared_observations':len(records),'distinct_observation_ids':len(independent),'records':[{'observation_id':r.get('observation_id'),'observation_time':r.get('observation_time'),'bandpass':r.get('bandpass')} for r in records]},reasons or ['Verified relative calibration, matching spectral responses and spatial registration'],['Supply independently prepared observations and a method-specific comparison/calibration contract'])

def assess(records,policy=Policy()):
    if not records:raise ValueError('No verified observations')
    f=records[0];out={};base={'product_id':f['product_id'],'analysis_pixels':f['analysis_pixels'],'analysis_fraction':f['analysis_fraction'],'background_pixels':f['background_pixels'],'background_fraction':f['background_fraction'],'background_occupied_fraction':f['background_occupied_fraction'],'analysis_occupied_fraction':f['analysis_occupied_fraction'],'references':f['references']}
    missing=[code for key,code in [('image','IMAGE_MISSING'),('units','UNITS_UNVERIFIED'),('wcs','SPATIAL_WCS_MISSING')] if not f.get(key)]
    if f['analysis_pixels']==0:missing.append('NO_USABLE_PIXELS')
    out['sky_visualization']=decision('blocked' if missing else 'ready',missing or ['SPATIAL_DISPLAY_REQUIREMENTS_MET'],base,missing,warnings=['Spatial display only; no spectral maps or scientific accuracy claim'])
    missing=[code for key,code in [('image','IMAGE_MISSING'),('variance','VARIANCE_MISSING'),('noise','NOISE_INFORMATION_MISSING'),('wcs','SPATIAL_WCS_MISSING')] if not f.get(key)]
    if f['analysis_fraction']<policy.min_analysis_fraction:missing.append('INSUFFICIENT_ANALYSIS_SUPPORT')
    out['source_detection']=decision('blocked' if missing else 'conditional',missing or ['DETECTION_METHOD_NOT_QUALIFIED','BACKGROUND_NOT_ESTIMATED'],base,missing or ['Algorithm-specific noise and background treatment'],['Select and validate a detection method; test reliability before reporting discoveries'],['Small or clustered background sample limits methods requiring local background'])
    bg=[]
    if f['background_pixels']<policy.min_background_pixels:bg.append('BACKGROUND_COUNT_LOW')
    if f['background_fraction']<policy.min_background_fraction:bg.append('BACKGROUND_FRACTION_LOW')
    if f['background_occupied_fraction']<policy.min_background_occupied_fraction:bg.append('BACKGROUND_SPATIALLY_CLUSTERED')
    if not f.get('variance'):bg.append('VARIANCE_MISSING')
    out['background_estimation']=decision('blocked' if bg else 'conditional',bg or ['BACKGROUND_ESTIMATOR_UNSPECIFIED'],base,bg or ['Estimator-specific sample sufficiency criterion'],['Select global/local estimator and validate sampling adequacy'],['Thresholds are VEGA operational screening, not NASA requirements'])
    photo=[]
    for key,code in [('image','IMAGE_MISSING'),('units','UNITS_UNVERIFIED'),('variance','VARIANCE_MISSING'),('wcs','SPATIAL_WCS_MISSING')]:
        if not f.get(key):photo.append(code)
    out['photometry']=decision('blocked' if photo else 'conditional',photo or ['SOLID_ANGLE_MAP_MISSING','PHOTOMETRIC_METHOD_CALIBRATION_MISSING','BACKGROUND_NOT_ESTIMATED'],base,photo or ['Pixel solid angles, calibration/aperture corrections and validated background/PSF method'],['Qualify surface-brightness, flux and spectrophotometry methods separately'],['Summing MJy/sr is not a flux in Jy'])
    out['photometry']['methods']={'preliminary_surface_brightness':decision('blocked' if photo else 'conditional',photo or ['PRELIMINARY_SIGNAL_ONLY'],base,photo or ['Define measurement and uncertainty/background method']), 'calibrated_flux':decision('blocked',['SOLID_ANGLE_MAP_MISSING','PHOTOMETRIC_METHOD_CALIBRATION_MISSING']+([] if f.get('epsf') else ['EPSF_MISSING']),{'epsf_available':f.get('epsf')},['Verified solid-angle map and calibrated method']), 'precise_spectrophotometry':decision('blocked',['SCIENCE_SPECTRAL_CALIBRATION_MISSING'],{'spectral_table_valid':f.get('spectral_table')},['CWAVE/CBAND science calibration and a validated spectrophotometry method'])}
    out['temporal_comparison']=temporal(records)
    out['spectral_analysis']=decision('blocked',['SCIENCE_SPECTRAL_CALIBRATION_MISSING']+([] if f.get('spectral_maps') else ['SPECTRAL_MAPS_MISSING']),{'spectral_table_valid':f.get('spectral_table'),'spectral_maps_available':f.get('spectral_maps'),'epsf_available':f.get('epsf')},['Validated wavelength/bandwidth calibration for scientific measurements'],['Supply appropriate CWAVE/CBAND science calibration and method-specific validation'],['WCS-WAVE alone is visualization metadata'])
    return out
