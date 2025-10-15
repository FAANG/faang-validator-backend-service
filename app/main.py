import json
import asyncio
from uuid import uuid4
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.conversions.file_processor import parse_contents_api
from app.validations.unified_validator import UnifiedFAANGValidator
from app.sockets import SocketServer

sockets = SocketServer()

app = FastAPI(
    title="FAANG Validator API",
    description="API for validating FAANG data",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sockets.router)


@app.on_event("startup")
async def _debug_routes():
    for r in app.router.routes:
        try:
            print(type(r).__name__, getattr(r, "path", None))
        except Exception:
            pass


@app.get("/")
async def root():
    return {"message": "Welcome to FAANG Validator API", "status": "operational"}


def _stats(results):
    if not isinstance(results, list):
        return {"total": 0, "valid": 0, "invalid": 0}
    v = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "valid")
    iv = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "invalid")
    return {"total": len(results), "valid": v, "invalid": iv}


async def _process_validation(contents: bytes, filename: str, client_id: str | None):
    job_id = uuid4().hex
    output_file = "validation_results.json"

    async def ws_send(payload: dict):
        if client_id:
            await sockets.hub.send_to(client_id, payload | {"job_id": job_id})

    try:
        if client_id:
            await ws_send({"type": "status", "stage": "received"})

        records, sheet_names, error_message = await asyncio.to_thread(parse_contents_api, contents, filename)

        if error_message:
            await ws_send({"type": "error", "detail": error_message})
            if client_id:
                return None
            raise HTTPException(status_code=400, detail=error_message)

        if not sheet_names:
            detail = "No valid sheets found in the file."
            await ws_send({"type": "error", "detail": detail})
            if client_id:
                return None
            raise HTTPException(status_code=400, detail=detail)

        validator = UnifiedFAANGValidator()

        print("FAANG Sample Validation")
        print("=" * 50)
        print(f"Supported sample types: {', '.join(validator.get_supported_types())}")
        print()

        if not records:
            results = []
        else:
            if client_id:
                await ws_send({"type": "status", "stage": "validating"})
            results = await asyncio.to_thread(
                validator.validate_all_records,
                records,
                validate_relationships=True,
                validate_ontology_text=True,
            )

        report = await asyncio.to_thread(validator.generate_unified_report, results)
        print(report)

        biosample_exports = await asyncio.to_thread(validator.export_valid_samples_to_biosample, results)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(
                {'validation_results': results, 'biosample_exports': biosample_exports},
                f, indent=2, default=str
            )
        print(f"\nResults saved to: {output_file}")

        if client_id:
            await ws_send({
                "type": "result",
                "report": report,
                "stats": _stats(results),
                "output_file": output_file
            })
            await ws_send({"type": "done", "output_file": output_file})

        return {
            "job_id": job_id,
            "validation_results": results,
            "biosample_exports": biosample_exports,
            "report": report,
            "output_file": output_file
        }

    except HTTPException:
        if client_id:
            return None
        raise
    except Exception as e:
        await ws_send({"type": "error", "detail": str(e)})
        if client_id:
            return None
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate")
async def validate_file(
    file: UploadFile = File(...),
    x_client_id: str | None = Header(default=None, convert_underscores=False),
    client_id: str | None = Query(default=None),
):
    contents = await file.read()
    cid = client_id or x_client_id

    if cid:
        asyncio.create_task(_process_validation(contents, file.filename, cid))
        return JSONResponse({"status": "accepted", "client_id": cid}, status_code=202)

    data = await _process_validation(contents, file.filename, None)
    if data is None:
        raise HTTPException(status_code=500, detail="Internal error during validation.")
    return {
        "validation_results": data["validation_results"],
        "biosample_exports": data["biosample_exports"]
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
