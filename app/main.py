from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import json
import traceback

from app.conversions.file_processor import parse_contents_api
from app.profiler import cprofiled
from app.validations.unified_validator import UnifiedFAANGValidator

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


@app.post("/validate", response_model=ValidationResponse)
async def validate_data(request: ValidationRequest):
    try:
        if request.validate_ontology_text:
            print("Pre-fetching ontology terms...")
            await validator.prefetch_all_ontology_terms_async(request.data)

        if request.validate_relationships:
            print("Pre-fetching BioSample IDs...")
            await validator.prefetch_all_biosample_ids_async(request.data)

        print("Running validation...")
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
async def validate_file(file: UploadFile = File(...)):
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
            print("Pre-fetching ontology terms...")
            await validator.prefetch_all_ontology_terms_async(records)

            print("Pre-fetching BioSample IDs...")
            await validator.prefetch_all_biosample_ids_async(records)

            print("Running validation...")
            results = validator.validate_all_records(
                records,
                validate_relationships=True,
                validate_ontology_text=True,
            )

            try:
                import json

                total_summary = results.get("total_summary", {}) or {}
                print("DEBUG total_summary:", total_summary)

                results_by_type = results.get("results_by_type", {}) or {}

                for st, st_data in results_by_type.items():
                    st_key = st.replace(" ", "_")
                    valid_key = f"valid_{st_key}s"
                    invalid_key = f"invalid_{st_key}s"
                    if invalid_key.endswith("ss"):
                        invalid_key = invalid_key[:-1]

                    v = len(st_data.get(valid_key) or [])
                    iv = len(st_data.get(invalid_key) or [])
                    print(f"DEBUG type={st!r}: valid={v}, invalid={iv}")

                for st, st_data in results_by_type.items():
                    st_key = st.replace(" ", "_")
                    invalid_key = f"invalid_{st_key}s"
                    if invalid_key.endswith("ss"):
                        invalid_key = invalid_key[:-1]

                    invalid_rows = st_data.get(invalid_key) or []
                    if not invalid_rows:
                        continue

                    print(f"\nDEBUG invalid rows for {st!r}: count={len(invalid_rows)}")
                    for row in invalid_rows:
                        print("-" * 60)
                        print("sample_name:", row.get("sample_name"))
                        print("errors:")
                        print(json.dumps(row.get("errors"), indent=2, ensure_ascii=False))
                        print("warnings:", row.get("warnings"))
                        data = row.get("data") or {}
                        print("data keys:", list(data.keys()))
                        print()
            except Exception as dbg_e:
                print("DEBUG printing failed:", dbg_e)

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

        print(f"Submitting to BioSamples via Webin: mode={request.mode}")

        result = validator.submit_to_biosamples(
            validation_results=request.validation_results,
            webin_username=request.webin_username,
            webin_password=request.webin_password,
            domain=None,
            mode=request.mode,
            update_existing=request.update_existing
        )

        if result['success']:
            return SubmissionResponse(
                success=True,
                message=f"Successfully submitted {result['submitted_count']} samples to BioSamples",
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
