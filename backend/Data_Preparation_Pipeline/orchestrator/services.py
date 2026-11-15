"""Public interfaces of the nine stages, replaceable for offline integration tests."""
from dataclasses import dataclass
from typing import Callable
from user_input import create_request,save_request
from request_validation import validate_request,save_report
from archive_search import search,save_results,SIASettings
from data_download import download_batch,load_catalog,build_url,Limits
from fits_extraction import extract
from technical_validation import validate_extraction
from scientific_quality_validation import evaluate_quality
from analysis_readiness import evaluate_readiness,InputReferences
from algorithm_inputs import prepare_packages,load_package
@dataclass
class Services:
    create_request:Callable=create_request
    save_request:Callable=save_request
    validate_request:Callable=validate_request
    save_report:Callable=save_report
    search:Callable=search
    save_results:Callable=save_results
    download_batch:Callable=download_batch
    load_catalog:Callable=load_catalog
    build_url:Callable=build_url
    extract:Callable=extract
    validate_extraction:Callable=validate_extraction
    evaluate_quality:Callable=evaluate_quality
    evaluate_readiness:Callable=evaluate_readiness
    prepare_packages:Callable=prepare_packages
    load_package:Callable=load_package
