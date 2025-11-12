import cProfile
import io
import pstats
import datetime
import functools
import inspect
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import json
import traceback

from app.conversions.file_processor import parse_contents_api
from app.validations.unified_validator import UnifiedFAANGValidator

# -----------------------
# Profiling utilities
# -----------------------

def cprofiled(sortby: str = "cumtime", limit: int = 30):
    """
    Decorator that profiles a function (works for sync and async).
    Prints top 'limit' rows sorted by 'sortby' and returns the function's result.
    """
    def decorate(func):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def aw(*args, **kwargs):
                pr = cProfile.Profile(); pr.enable()
                try:
                    return await func(*args, **kwargs)
                finally:
                    pr.disable()
                    s = io.StringIO()
                    pstats.Stats(pr, stream=s).strip_dirs().sort_stats(sortby).print_stats(limit)
                    print(f"\n--- cProfile ({func.__name__}) ---\n{s.getvalue()}")
            return aw
        else:
            @functools.wraps(func)
            def w(*args, **kwargs):
                pr = cProfile.Profile(); pr.enable()
                try:
                    return func(*args, **kwargs)
                finally:
                    pr.disable()
                    s = io.StringIO()
                    pstats.Stats(pr, stream=s).strip_dirs().sort_stats(sortby).print_stats(limit)
                    print(f"\n--- cProfile ({func.__name__}) ---\n{s.getvalue()}")
            return w
    return decorate


@contextmanager
def profile_block(name: str = "block", sortby: str = "cumtime", limit: int = 30):
    """Context manager to profile an arbitrary block of code."""
    pr = cProfile.Profile()
    pr.enable()
    try:
        yield
    finally:
        pr.disable()
        s = io.StringIO()
        pstats.Stats(pr, stream=s).strip_dirs().sort_stats(sortby).print_stats(limit)
        print(f"\n--- cProfile ({name}) ---\n{s.getvalue()}")


app = FastAPI(
    title="FAANG Validation API",
    description="API for validating FAANG sample and metadata submissions",
    version="1.0.0"
)

validator = UnifiedFAANGValidator()

# ---------------
# Per-request cProfile middleware (enable with ?profile=1)
# ---------------
@app.middleware("http")
async def cprofile_middleware(request: Request, call_next):
    if request.query_params.get("profile") != "1":
        return await call_next(request)

    pr = cProfile.Profile()
    pr.enable()
    try:
        response = await call_next(request)
        return response
    finally:
        pr.disable()
        s = io.StringIO()
        pstats.Stats(pr, stream=s).strip_dirs().sort_stats("cumtime").print_stats(40)
        text = s.getvalue()

        # Save a timestamped report file per request
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_path = request.url.path.strip("/").replace("/", "_") or "root"
        fname = f"profile-{safe_path}-{stamp}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(text)

        # Also print to console
        print(f"\n--- cProfile ({request.url.path}) ---\n{text}")


class ValidationRequest(BaseModel):
    data: Dict[str, List[Dict[str, Any]]]
    validate_relationships: bool = True
    validate_ontology_text: bool = True


class ValidationResponse(BaseModel):
    status: str
    message: str
    results: Optional[Dict[str, Any]] = None
    report: Optional[str] = None


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


# Example of profiling just the heavy calls inside the endpoint:
@app.post("/validate", response_model=ValidationResponse)
async def validate_data(request: ValidationRequest):
    try:
        # Profile the prefetch phase as a block
        if request.validate_ontology_text or request.validate_relationships:
            with profile_block("prefetch_phase"):
                if request.validate_ontology_text:
                    await validator.prefetch_all_ontology_terms_async(request.data)
                if request.validate_relationships:
                    await validator.prefetch_all_biosample_ids_async(request.data)

        # Profile validate/report generation function-level:
        @cprofiled()
        def run_validation_and_report():
            results_local = validator.validate_all_records(
                request.data,
                validate_relationships=request.validate_relationships,
                validate_ontology_text=request.validate_ontology_text
            )
            report_local = validator.generate_unified_report(results_local)
            return results_local, report_local

        results, report = run_validation_and_report()

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


@app.post("/validate-file")
async def validate_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        records, sheet_names, headers_map, error_message = parse_contents_api(contents, file.filename)
        if error_message:
            raise HTTPException(status_code=400, detail=error_message)
        if not sheet_names:
            raise HTTPException(status_code=400, detail="No valid sheets found in the file.")

        print("FAANG Sample Validation")
        print("=" * 50)

        if not records:
            results = []
            report = validator.generate_unified_report(results)
        else:
            # Profile prefetch + validation separately for visibility
            with profile_block("prefetch_phase_file"):
                await validator.prefetch_all_ontology_terms_async(records)
                await validator.prefetch_all_biosample_ids_async(records)

            @cprofiled()
            def run_validation_and_report_file():
                res = validator.validate_all_records(
                    records,
                    validate_relationships=True,
                    validate_ontology_text=True
                )
                rep = validator.generate_unified_report(res)
                return res, rep

            results, report = run_validation_and_report_file()

        return {
            "status": "success",
            "filename": file.filename,
            "message": "File validated successfully",
            "results": results,
            "report": report
        }

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


@app.get("/export-valid-samples")
async def export_valid_samples_endpoint():
    return {
        "message": "Use POST /validate endpoint first, then access results.biosample_exports from the response"
    }


if __name__ == "__main__":
    import uvicorn
    # Don’t use cProfile.run('main()') here; it doesn’t call anything meaningful.
    # Run normally (use ?profile=1 on requests), or profile the whole process like this:
    #   python -m cProfile -o server.prof -m uvicorn app:app
    # and visualize with:
    #   pip install snakeviz
    #   snakeviz server.prof
    uvicorn.run(app, host="0.0.0.0", port=8000)
