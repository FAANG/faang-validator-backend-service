from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Union, Literal, Optional
from app.validations.validation_utils import strip_and_convert_empty_to_none


class SecondaryProjectItem(BaseModel):
    """Model for secondary project item in array."""
    value: Literal[
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
    ] = Field(..., alias="value")

    @field_validator('value', mode='before')
    def validate_secondary_project_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v


class FAANGFAANGAnalysis(BaseModel):
    """
    Pydantic model for FAANG analysis metadata.
    Based on faang_analyses_faang.metadata_rules.json
    """
    # required fields
    project: Literal["FAANG", "restricted access"] = Field(
        ...,
        alias="project",
        description="State that the project is 'FAANG'."
    )
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
        alias="assay type",
        description="The type of experiment analysis data was derived from."
    )
    analysis_protocol: Union[HttpUrl, Literal["restricted access"]] = Field(
        ...,
        alias="analysis protocol",
        description="Link to the description of the analysis protocol."
    )

    # required fields (alias has mandatory: "mandatory" in JSON)
    alias: str = Field(
        ...,
        alias="alias",
        description="The alias of the analysis."
    )
    secondary_project: Optional[List[SecondaryProjectItem]] = Field(
        None,
        alias="secondary project",
        description="State the secondary project(s) that this data belongs to."
    )
    analysis_code: Optional[Union[HttpUrl, Literal["restricted access"]]] = Field(
        None,
        alias="analysis code",
        description="Link to the repository that contains the code used in the analysis.",
        json_schema_extra={"recommended": True}
    )
    analysis_code_version: Optional[Union[str, Literal["restricted access"]]] = Field(
        None,
        alias="analysis version",
        description="Version of the analysis code used in the analysis.",
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
        alias="reference genome",
        description="The reference genome used in the analysis.",
        json_schema_extra={"recommended": True}
    )
    nextflow_config_url: Optional[HttpUrl] = Field(
        None,
        alias="nextflow config url",
        description="Url of uploaded nextflow configuration file."
    )
    nextflow_spreadsheet_url: Optional[HttpUrl] = Field(
        None,
        alias="nextflow spreadsheet url",
        description="Url of uploaded nextflow spreadsheet file."
    )

    @field_validator('project', 'assay_type', 'analysis_protocol', mode='before')
    def validate_object_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v

    @field_validator('alias', mode='before')
    def validate_alias_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        if not v or v == "":
            return None
        return v

    @field_validator('secondary_project', mode='before')
    def validate_secondary_project_array(cls, v):
        if isinstance(v, list):
            return [item if isinstance(item, dict) else {'value': item} for item in v]
        return v

    @field_validator('analysis_code', 'analysis_code_version', mode='before')
    def validate_optional_object_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        if not v or v == "":
            return None
        return v

    @field_validator('reference_genome', mode='before')
    def validate_reference_genome_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        if not v or v == "":
            return None
        return v

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"

