import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.conversions.file_processor import parse_contents_api
from app.validations.unified_validator import UnifiedFAANGValidator

app = FastAPI(
    title="FAANG Validator API",
    description="API for validating FAANG data",
    version="0.1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
@app.get("/")
async def root():
    """
    Root endpoint that returns a welcome message.
    """
    return {
        "message": "Welcome to FAANG Validator API",
        "status": "operational"
    }


@app.post("/validate")
async def validate_file(file: UploadFile = File(...)):
    """
    Validate an uploaded file against FAANG standards.

    Args:
        file: The file to validate

    Returns:
        dict: Validation results
    """
    try:
        # Read file contents
        contents = await file.read()

        # Parse file contents - now returns all sheets
        all_sheets_data, sheet_names, error_message = parse_contents_api(contents, file.filename)

        if error_message:
            raise HTTPException(status_code=400, detail=error_message)

        # Check if sheet_names is empty or None
        if not sheet_names:
            raise HTTPException(status_code=400, detail="No valid sheets found in the file.")

        # For validation, we'll use the first sheet's data
        # This maintains compatibility with the existing validation logic
        first_sheet_name = sheet_names[0]
        records = all_sheets_data[first_sheet_name]


        validator = UnifiedFAANGValidator()

        print("FAANG Sample Validation")
        print("=" * 50)
        print(f"Supported sample types: {', '.join(validator.get_supported_types())}")
        print()

        # validation
        results = validator.validate_all_records(
            records,
            validate_relationships=True,
            validate_ontology_text=True
        )

        report = validator.generate_unified_report(results)
        print(report)

        # BioSample format
        biosample_exports = validator.export_valid_samples_to_biosample(results)

        # if biosample_exports:
        #     print("\n" + "=" * 60)
        #     print("BIOSAMPLE EXPORTS")
        #     print("=" * 60)
        #
        #     for sample_type, exports in biosample_exports.items():
        #         print(f"\n{sample_type.upper()} SAMPLES:")
        #         print("-" * 30)
        #
        #         for export in exports:
        #             print(f"\nSample: {export['sample_name']}")
        #             print(json.dumps(export['biosample_format'], indent=2))

        # save results to file
        save_results = True
        if save_results:
            output_file = "validation_results.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'validation_results': results,
                    'biosample_exports': biosample_exports
                }, f, indent=2, default=str)
            print(f"\nResults saved to: {output_file}")


        # Return validation results along with all sheets data
        return {
            "all_sheets_data": all_sheets_data,
            "sheet_names": sheet_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



