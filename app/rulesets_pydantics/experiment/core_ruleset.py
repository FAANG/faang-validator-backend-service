from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from app.validation.validation_utils import (
    validate_url,
    validate_date_format,
    validate_latitude,
    validate_longitude,
    validate_non_negative_numeric,
    strip_and_convert_empty_to_none
)


class ExperimentCoreMetadata(BaseModel):
    # required fields
    project: Literal["FAANG"] = Field(..., alias="Project")
    assay_type: Literal[
        "ATAC-seq",
        "ChIP-seq",
        "CAGE-seq",
        "whole genome sequencing assay",
        "DNase-Hypersensitivity seq",
        "Hi-C",
        "methylation profiling by high throughput sequencing",
        "microRNA profiling by high throughput sequencing",
        "RNA-seq of total RNA",
        "RNA-seq of coding RNA",
        "RNA-seq of non coding RNA",
        "transcription profiling by high throughput sequencing",
        "scRNA-seq",
        "ISO-Seq",
        "snATAC-seq",
        "restricted access"
    ] = Field(..., alias="Assay Type")
    
    sample_storage_processing: Literal[
        "cryopreservation in liquid nitrogen (dead tissue)",
        "cryopreservation in dry ice (dead tissue)",
        "cryopreservation of live cells in liquid nitrogen",
        "cryopreservation, other",
        "formalin fixed, unbuffered",
        "formalin fixed, buffered",
        "formalin fixed and paraffin embedded",
        "fresh",
        "restricted access"
    ] = Field(..., alias="Sample Storage Processing")
    
    sampling_to_preparation_interval: float = Field(..., alias="Sampling to Preparation Interval")
    sampling_to_preparation_interval_unit: Literal[
        "minutes", "hours", "days", "weeks", "months", "years",
        "minute", "hour", "day", "week", "month", "year",
        "restricted access"
    ] = Field(..., alias="Unit")
    
    extraction_protocol: str = Field(..., alias="Extraction Protocol")

    # Optional fields
    sample_descriptor: Optional[str] = Field(None, alias="Sample Descriptor")
    experiment_alias: Optional[str] = Field(None, alias="Experiment Alias")

    secondary_project: Optional[List[Literal[
        "AQUA-FAANG",
        "GENE-SWitCH",
        "BovReg",
        "Bovine-FAANG",
        "EFFICACE",
        "GEroNIMO",
        "RUMIGEN",
        "Equine-FAANG",
        "Holoruminant",
        "USPIGFAANG"
    ]]] = Field(None, alias="Secondary Project")
    
    sample_storage: Optional[Literal[
        "ambient temperature",
        "cut slide",
        "fresh",
        "frozen, -70 freezer",
        "frozen, -150 freezer",
        "frozen, liquid nitrogen",
        "frozen, vapor phase",
        "paraffin block",
        "RNAlater, frozen",
        "TRIzol, frozen"
    ]] = Field(None, alias="Sample Storage")
    
    experimental_protocol: Optional[str] = Field(None, alias="Experimental Protocol")
    
    # Recommended fields
    library_preparation_location: Optional[str] = Field(
        None, alias="Library Preparation Location",
        json_schema_extra={"recommended": True}
    )
    library_preparation_location_longitude: Optional[float] = Field(
        None, alias="Library Preparation Location Longitude",
        json_schema_extra={"recommended": True}
    )
    library_preparation_location_longitude_unit: Optional[Literal[
        "decimal degrees",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access"
    ]] = Field(None, alias="Library Preparation Location Longitude Unit",
               json_schema_extra={"recommended": True})
    
    library_preparation_location_latitude: Optional[float] = Field(
        None, alias="Library Preparation Location Latitude",
        json_schema_extra={"recommended": True}
    )
    library_preparation_location_latitude_unit: Optional[Literal[
        "decimal degrees",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access"
    ]] = Field(None, alias="Library Preparation Location Latitude Unit",
               json_schema_extra={"recommended": True})
    
    library_preparation_date: Optional[str] = Field(
        None, alias="Library Preparation Date",
        json_schema_extra={"recommended": True}
    )
    library_preparation_date_unit: Optional[Literal[
        "YYYY-MM-DD", "YYYY-MM", "YYYY",
        "not applicable", "not collected", "not provided", "restricted access"
    ]] = Field(None, alias="Library Preparation Date Unit",
               json_schema_extra={"recommended": True})
    
    sequencing_location: Optional[str] = Field(
        None, alias="Sequencing Location",
        json_schema_extra={"recommended": True}
    )
    sequencing_location_longitude: Optional[float] = Field(
        None, alias="Sequencing Location Longitude",
        json_schema_extra={"recommended": True}
    )
    sequencing_location_longitude_unit: Optional[Literal[
        "decimal degrees",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access"
    ]] = Field(None, alias="Sequencing Location Longitude Unit",
               json_schema_extra={"recommended": True})
    
    sequencing_location_latitude: Optional[float] = Field(
        None, alias="Sequencing Location Latitude",
        json_schema_extra={"recommended": True}
    )
    sequencing_location_latitude_unit: Optional[Literal[
        "decimal degrees",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access"
    ]] = Field(None, alias="Sequencing Location Latitude Unit",
               json_schema_extra={"recommended": True})
    
    sequencing_date: Optional[str] = Field(
        None, alias="Sequencing Date",
        json_schema_extra={"recommended": True}
    )
    sequencing_date_unit: Optional[Literal[
        "YYYY-MM-DD", "YYYY-MM", "YYYY",
        "not applicable", "not collected", "not provided", "restricted access"
    ]] = Field(None, alias="Sequencing Date Unit",
               json_schema_extra={"recommended": True})
    
    # Validators
    @field_validator('extraction_protocol')
    def validate_extraction_protocol_url(cls, v):
        if v == "restricted access":
            return v
        return validate_url(v, field_name="Extraction Protocol", allow_restricted=True)
    
    @field_validator('experimental_protocol')
    def validate_experimental_protocol_url(cls, v):
        if not v:
            return v
        return validate_url(v, field_name="Experimental Protocol", allow_restricted=False)
    
    @field_validator('library_preparation_date')
    def validate_library_prep_date_format(cls, v, info):
        values = info.data
        unit = values.get('Library Preparation Date Unit') or values.get('library_preparation_date_unit')
        return validate_date_format(v, unit, "Library Preparation Date")
    
    @field_validator('sequencing_date')
    def validate_sequencing_date_format(cls, v, info):
        values = info.data
        unit = values.get('Sequencing Date Unit') or values.get('sequencing_date_unit')
        return validate_date_format(v, unit, "Sequencing Date")
    
    @field_validator('library_preparation_location_latitude', 'sequencing_location_latitude', mode='before')
    def validate_latitude_field(cls, v):
        if v in ["not applicable", "not collected", "not provided", "restricted access"]:
            return v
        return validate_latitude(v)
    
    @field_validator('library_preparation_location_longitude', 'sequencing_location_longitude', mode='before')
    def validate_longitude_field(cls, v):
        if v in ["not applicable", "not collected", "not provided", "restricted access"]:
            return v
        return validate_longitude(v)
    
    @field_validator('sampling_to_preparation_interval', mode='before')
    def validate_sampling_interval(cls, v):
        if v == "restricted access":
            return v
        return validate_non_negative_numeric(v, "Sampling to Preparation Interval", allow_restricted=True)
    
    @field_validator('secondary_project', mode='before')
    def validate_secondary_project(cls, v):
        if not v:
            return None
        if isinstance(v, str):
            if v.strip() == "":
                return None
            v = [v]
        if isinstance(v, list):
            filtered = [item for item in v if item and isinstance(item, str) and item.strip()]
            return filtered if filtered else None
        return v
    
    # Convert empty strings to None for optional fields
    @field_validator(
        'sample_storage', 'experimental_protocol', 'library_preparation_location',
        'sequencing_location', 'library_preparation_date', 'sequencing_date',
        'library_preparation_date_unit', 'sequencing_date_unit',
        'library_preparation_location_longitude_unit', 'library_preparation_location_latitude_unit',
        'sequencing_location_longitude_unit', 'sequencing_location_latitude_unit',
        mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
