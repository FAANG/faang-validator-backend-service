from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Union, Literal, Optional
from app.validation.validation_utils import strip_and_convert_empty_to_none, validate_protocol_url


class FAANGAnalysis(BaseModel):
    # required fields
    project: Literal["FAANG", "restricted access"] = Field(..., alias="Project")

    assay_type: Literal[
        "ATAC-seq",
        "ChIP-seq",
        "transcription profiling by high throughput sequencing",
        "whole genome sequencing assay",
        "CAGE-seq",
        "DNase-Hypersensitivity seq",
        "Hi-C",
        "methylation profiling by high throughput sequencing",
        "microRNA profiling by high throughput sequencing",
        "RNA-seq of total RNA",
        "RNA-seq of coding RNA",
        "RNA-seq of non coding RNA",
        "ISO-Seq",
        "restricted access"
    ] = Field(
        ...,
        alias="Assay Type")

    analysis_protocol: Union[str, Literal["restricted access"]] = Field(
        ...,
        alias="Analysis Protocol")

    alias: str = Field(
        ...,
        alias="Alias"
    )

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
    ]]] = Field(
        None,
        alias="Secondary Project")

    # recommended fields
    analysis_code: Optional[Union[str, Literal["restricted access"]]] = Field(
        None,
        alias="Analysis Code",
        json_schema_extra={"recommended": True}
    )

    analysis_code_version: Optional[Union[str, Literal["restricted access"]]] = Field(
        None,
        alias="Analysis Code Version",
        json_schema_extra={"recommended": True}
    )

    reference_genome: Optional[Literal[
        "Sscrofa11.1",
        "EquCab3.0",
        "Oar_v3.1",
        "ARS-UCD1.2",
        "GRCg6a",
        "ARS1",
        "GRCg7b",
        "GRCg7w",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access"
    ]] = Field(
        None,
        alias="Reference Genome",
        json_schema_extra={"recommended": True}
    )

    # optional fields
    nextflow_config_url: Optional[Union[str, Literal["restricted access"]]] = Field(
        None,
        alias="Nextflow Config Url"
    )

    nextflow_spreadsheet_url: Optional[Union[str, Literal["restricted access"]]] = Field(
        None,
        alias="Nextflow Spreadsheet Url"
    )


    @field_validator('analysis_protocol', 'analysis_code', 'nextflow_config_url', 'nextflow_spreadsheet_url')
    def validate_url_fields(cls, v):
        return validate_protocol_url(v, allow_restricted=True)

    @field_validator('alias')
    def validate_alias_not_empty(cls, v):
        if not v or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Alias is required and cannot be empty")
        return v.strip() if isinstance(v, str) else v

    @field_validator('secondary_project', mode='before')
    def validate_secondary_project(cls, v):
        if not v:
            return None

        if isinstance(v, list):
            result = [item.strip() for item in v if item and str(item).strip()]
            return result if result else None

        if isinstance(v, str) and v.strip():
            return [v.strip()]

        return None

    @field_validator('analysis_code_version', 'reference_genome', mode='before')
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"