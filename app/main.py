from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional, Literal
import json
import traceback

from app.conversions.file_processor import parse_contents_api
from app.profiler import cprofiled
from app.validation.unified_validator import UnifiedFAANGValidator
from app.submission import BioSampleSubmitter, ExperimentSubmitter, AnalysisSubmitter

app = FastAPI(
    title="FAANG Validation API",
    description="API for validating FAANG sample and metadata submissions",
    version="1.0.0"
)

validator = UnifiedFAANGValidator()


class ValidationRequest(BaseModel):
    data: Dict[str, List[Dict[str, Any]]]
    validate_relationships: bool = True
    validate_ontology_text: bool = True
    data_type: Literal["sample", "experiment", "analysis"]


class ValidationResponse(BaseModel):
    status: str
    message: str
    results: Optional[Dict[str, Any]] = None
    report: Optional[str] = None



class SubmissionRequest(BaseModel):
    validation_results: Dict[str, Any]
    webin_username: str
    webin_password: str
    domain: Optional[str] = None
    mode: str = "test"
    update_existing: bool = False


class SubmissionResponse(BaseModel):
    success: bool
    message: str
    biosamples_ids: Optional[Dict[str, str]] = None
    submitted_count: Optional[int] = None
    errors: Optional[List[str]] = None
      
      
class ValidationDataRequest(BaseModel):
    data: dict[str, list[dict[str, Any]]]
    data_type: Literal["sample", "experiment", "analysis"]


class AnalysisSubmissionRequest(BaseModel):
    data: Dict[str, Any]
    webin_username: str
    webin_password: str
    mode: str
    action: str = "submission"


class AnalysisSubmissionResponse(BaseModel):
    success: bool
    message: str
    submission_results: Optional[str] = None
    errors: Optional[List[str]] = None
    info_messages: Optional[List[str]] = None

class ExperimentSubmissionRequest(BaseModel):
    validation_results: Dict[str, Any]
    original_data: Dict[str, Any]  # original json with experiment ena, run, study, submission sheets
    webin_username: str
    webin_password: str
    mode: str
    action: str = "submission"


class ExperimentSubmissionResponse(BaseModel):
    success: bool
    message: str
    submission_results: Optional[str] = None
    errors: Optional[List[str]] = None
    info_messages: Optional[List[str]] = None


def normalize_experiment_ena_record(record: dict) -> dict:
    normalized = {}
    for key, value in record.items():
        if isinstance(value, list):
            if len(value) >= 1:
                normalized[key] = value[0]
            else:
                normalized[key] = ""
        else:
            normalized[key] = value
    return normalized

def normalize_run_record(record: dict) -> dict:
    field_mappings = {
        'Run center': 'Run Center',
        'Run date': 'Run Date',
        'Experiment Ref': 'Experiment Ref',
        'Checksum Method': 'Checksum Method',
        'Filename pair': 'Filename Pair',
        'Filetype pair': 'Filetype Pair',
        'Checksum method pair': 'Checksum Method Pair',
        'Checksum pair': 'Checksum Pair'
    }

    normalized = {}
    for key, value in record.items():
        normalized_key = field_mappings.get(key, key)
        normalized[normalized_key] = value

    return normalized


# Health check endpoint
@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "FAANG Validation API",
        "version": "1.0.0",
        "supported_sample_types": validator.get_supported_types()['sample_types'],
        "supported_metadata_types": validator.get_supported_types()['metadata_types']
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "validators": {
            "sample_validators": len(validator.validators),
            "metadata_validators": len(validator.metadata_validators)
        }
    }


@app.get("/supported-types")
async def get_supported_types():
    return validator.get_supported_types()


async def prefetch_data_by_type(data: Dict[str, List[Dict[str, Any]]], data_type: str):
    if data_type == "sample":
        print("Pre-fetching sample ontology terms...")
        await validator.prefetch_all_ontology_terms_async("sample", data)

        print("Pre-fetching BioSample IDs...")
        await validator.prefetch_all_biosample_ids_async(data)

    elif data_type == "experiment":
        print("Pre-fetching experiment ontology terms...")
        await validator.prefetch_all_ontology_terms_async("experiment", data)

        print("Pre-fetching ENA experiment IDs...")
        await validator.prefetch_ena_experiment_ids_async(data)

    elif data_type == "analysis":
        print("Skipping pre-fetch for analysis data (no ontology terms or relationships)")

@app.post("/validate", response_model=ValidationResponse)
async def validate_data(request: ValidationRequest):
    try:
        await prefetch_data_by_type(request.data, request.data_type)

        print(f"Running validation for data_type: {request.data_type}...")
        results = validator.validate_all_records(
            request.data,
            validate_relationships=request.validate_relationships,
            validate_ontology_text=request.validate_ontology_text
        )

        # report
        report = validator.generate_unified_report(results)

        return ValidationResponse(
            status="success",
            message="Validation completed successfully",
            results=results,
            report=report
        )

    except Exception as e:
        print(f"Error during validation: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Validation failed",
                "message": str(e),
                "type": type(e).__name__
            }
        )


@cprofiled(limit=25)
@app.post("/validate-file")
async def validate_file(
    file: UploadFile = File(...),
    data_type: Literal["sample", "experiment", "analysis"] = Query(
        ...,
        description="Type of data in the file: 'sample', 'experiment', or 'analysis'"
    ),
    validate_relationships: bool = Query(
        default=True,
        description="Whether to validate cross-record relationships"
    ),
    validate_ontology_text: bool = Query(
        default=True,
        description="Whether to validate ontology term text matches"
    )
):
    try:
        contents = await file.read()

        records, sheet_names, error_message = parse_contents_api(contents, file.filename)

        if error_message:
            raise HTTPException(status_code=400, detail=error_message)

        if not sheet_names:
            raise HTTPException(status_code=400, detail="No valid sheets found in the file.")

        print("FAANG Sample Validation")
        print("=" * 50)
        print("Supported types:", validator.get_supported_types())
        print()

        if not records:
            results = {}
            report = ""
        else:
            await prefetch_data_by_type(records, data_type)

            print("Running validation...")
            results = validator.validate_all_records(
                records,
                validate_relationships=True,
                validate_ontology_text=True,
            )


            report = validator.generate_unified_report(results)

        return {
            "status": "success",
            "filename": file.filename,
            "message": "File validated successfully",
            "results": results,
            "report": report,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during validation: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Validation failed",
                "message": str(e),
                "type": type(e).__name__,
            },
        )


@app.get("/export-valid-samples")
async def export_valid_samples_endpoint():
    return {
        "message": "Use POST /validate endpoint first, then access results.biosample_exports from the response"
    }


@app.post("/submit-to-biosamples", response_model=SubmissionResponse)
async def submit_to_biosamples(request: SubmissionRequest):
    try:
        if request.mode not in ['test', 'prod']:
            raise HTTPException(
                status_code=400,
                detail="Mode must be 'test' or 'prod'"
            )


        submitter = BioSampleSubmitter(validator.sample_validators)
        result = submitter.submit_to_biosamples(
            validation_results=request.validation_results,
            webin_username=request.webin_username,
            webin_password=request.webin_password,
            domain=request.domain,
            mode=request.mode,
            update_existing=request.update_existing
        )

        if result['success']:
            action_word = "updated" if request.update_existing else "submitted"
            return SubmissionResponse(
                success=True,
                message=f"Successfully {action_word} {result['submitted_count']} samples to BioSamples",
                biosamples_ids=result['biosamples_ids'],
                submitted_count=result['submitted_count'],
                errors=result.get('errors', [])
            )
        else:
            return SubmissionResponse(
                success=False,
                message="Submission failed",
                errors=result.get('errors', [result.get('error', 'Unknown error')])
            )

    except Exception as e:
        print(f"Error during submission: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Submission failed",
                "message": str(e),
                "type": type(e).__name__
            }
        )



@app.post("/submit-analysis", response_model=AnalysisSubmissionResponse)
def submit_analysis(request: AnalysisSubmissionRequest):
    """
    Submit analysis records to ENA using the simplified public-only
    Analysis submission logic (no private submissions, no proxy samples).
    """
    try:
        if request.mode not in ["test", "prod"]:
            raise HTTPException(
                status_code=400,
                detail="Mode must be 'test' or 'prod'",
            )

        if request.action not in ["submission", "update"]:  # ← ADDED validation
            raise HTTPException(
                status_code=400,
                detail="Action must be 'submission' or 'update'",
            )

        credentials = {
            "username": request.webin_username,
            "password": request.webin_password,
            "mode": request.mode
        }
        print(f"Submitting to ENA via Webin: mode={request.mode}, action={request.action}")
        print(json.dumps(request.data))
        submitter = AnalysisSubmitter()

        result = submitter.submit_to_ena(
            results=request.data,
            credentials=credentials,
            action=request.action
        )

        action_word = "update" if request.action == "update" else "submission"
        if result.get("success"):
            return AnalysisSubmissionResponse(
                success=True,
                message=result.get("message", f"Successful analyses {action_word} in ENA"),
                submission_results=result.get("submission_results"),
                errors=result.get("errors"),
                info_messages=result.get("info_messages"),
            )

        return AnalysisSubmissionResponse(
            success=False,
            message=result.get("message", f"Analysis {action_word} to ENA failed"),
            submission_results=result.get("submission_results"),
            errors=result.get("errors", ["Unknown error"]),
            info_messages=result.get("info_messages"),
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during analysis {request.action}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Analysis {request.action} failed",
                "message": str(e),
                "type": type(e).__name__,
            },
        )


@app.post("/submit-experiment", response_model=ExperimentSubmissionResponse)
def submit_experiment(request: ExperimentSubmissionRequest):
    try:
        if request.mode not in ["test", "prod"]:
            raise HTTPException(
                status_code=400,
                detail="Mode must be 'test' or 'prod'",
            )

        if request.action not in ["submission", "update"]:
            raise HTTPException(
                status_code=400,
                detail="Action must be 'submission' or 'update'",
            )

        print(f"Preparing experiment submission: mode={request.mode}, action={request.action}")

        # Prepare the results by adding ENA-specific sheets from original data
        prepared_results = dict(request.validation_results)

        # Add experiment ena records
        if 'experiment ena' in request.original_data:
            if 'experiment_results' not in prepared_results:
                prepared_results['experiment_results'] = {}
            if 'experiment ena' not in prepared_results['experiment_results']:
                prepared_results['experiment_results']['experiment ena'] = {'valid': [], 'invalid': []}

            for record in request.original_data['experiment ena']:
                normalized_record = normalize_experiment_ena_record(record)
                prepared_results['experiment_results']['experiment ena']['valid'].append({
                    'model': normalized_record,
                    'data': normalized_record
                })
            print(f"Added {len(request.original_data['experiment ena'])} experiment ena records")

        # Add run records
        if 'run' in request.original_data:
            if 'metadata_results' not in prepared_results:
                prepared_results['metadata_results'] = {}
            if 'run' not in prepared_results['metadata_results']:
                prepared_results['metadata_results']['run'] = {'valid': [], 'invalid': []}

            for record in request.original_data['run']:
                normalized_record = normalize_run_record(record)
                prepared_results['metadata_results']['run']['valid'].append({
                    'model': normalized_record,
                    'data': normalized_record
                })
            print(f"Added {len(request.original_data['run'])} run records")

        # Add study records
        if 'study' in request.original_data:
            if 'metadata_results' not in prepared_results:
                prepared_results['metadata_results'] = {}
            if 'study' not in prepared_results['metadata_results']:
                prepared_results['metadata_results']['study'] = {'valid': [], 'invalid': []}

            for record in request.original_data['study']:
                prepared_results['metadata_results']['study']['valid'].append({
                    'model': record,
                    'data': record
                })
            print(f"Added {len(request.original_data['study'])} study records")

        # Add submission records
        if 'submission' in request.original_data:
            if 'metadata_results' not in prepared_results:
                prepared_results['metadata_results'] = {}
            if 'submission' not in prepared_results['metadata_results']:
                prepared_results['metadata_results']['submission'] = {'valid': [], 'invalid': []}

            for record in request.original_data['submission']:
                prepared_results['metadata_results']['submission']['valid'].append({
                    'model': record,
                    'data': record
                })
            print(f"Added {len(request.original_data['submission'])} submission records")

        # Prepare credentials
        credentials = {
            "username": request.webin_username,
            "password": request.webin_password,
            "mode": request.mode
        }

        print(f"Submitting to ENA: mode={request.mode}, action={request.action}")

        # Initialize the experiment submitter
        submitter = ExperimentSubmitter()

        # Submit to ENA
        result = submitter.submit_to_ena(
            results=prepared_results,
            credentials=credentials,
            action=request.action
        )

        action_word = "update" if request.action == "update" else "submission"
        if result.get("success"):
            return ExperimentSubmissionResponse(
                success=True,
                message=result.get("message", f"Successful experiments {action_word} in ENA"),
                submission_results=result.get("submission_results"),
                errors=result.get("errors"),
                info_messages=result.get("info_messages"),
            )

        return ExperimentSubmissionResponse(
            success=False,
            message=result.get("message", f"Experiment {action_word} to ENA failed"),
            submission_results=result.get("submission_results"),
            errors=result.get("errors", ["Unknown error"]),
            info_messages=result.get("info_messages"),
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during experiment {request.action}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Experiment {request.action} failed",
                "message": str(e),
                "type": type(e).__name__,
            },
        )


@cprofiled(limit=25)
@app.post("/validate-data")
async def validate_data(request: ValidationDataRequest):
        print("FAANG Validation")
        print("=" * 50)
        supported_types = validator.get_supported_types()
        print(f"Supported sample types: {', '.join(supported_types.get('sample_types', []))}")
        print(f"Supported experiment types: {', '.join(supported_types.get('experiment_types', []))}")
        print(f"Supported analysis types: {', '.join(supported_types.get('analysis_types', []))}")
        print(f"Supported metadata types: {', '.join(supported_types.get('metadata_types', []))}")
        print()

        # Check if records is empty
        if not request.data:
            results = []
        else:
            # validation
            await prefetch_data_by_type(request.data, request.data_type)

            print("Running validation...")
            results = validator.validate_all_records(
                request.data,
                validate_relationships=True,
                validate_ontology_text=True
            )

            # report
            report = validator.generate_unified_report(results)
            print(report)
            
            return {
                "status": "success",
                "message": "File validated successfully",
                "results": results,
                "report": report
            }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
