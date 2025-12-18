from pydantic import BaseModel, Field, field_validator
from typing import List, Union, Literal, Optional
from app.validations.validation_utils import strip_and_convert_empty_to_none


class ExperimentTypeItem(BaseModel):
    """Model for experiment type item in array."""
    value: Literal[
        "Whole Genome Sequencing",
        "Whole Transcriptome Sequencing",
        "Exome Sequencing",
        "Genotyping By Array",
        "Transcriptomics",
        "Curation",
        "Genotyping By Sequencing",
        "Target Sequencing",
        "restricted access"
    ] = Field(..., alias="value")

    @field_validator('value', mode='before')
    def validate_experiment_type_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v


class PlatformItem(BaseModel):
    """Model for platform item in array."""
    value: Literal[
        "Nimblegen 4.2M Probe Custom DNA Microarray",
        "Illumina NovaSeq 6000",
        "Illumina Genome Analyzer",
        "Illumina Genome Analyzer II",
        "Illumina Genome Analyzer IIx",
        "AB SOLiD System 2.0",
        "AB SOLiD System 3.0",
        "AB SOLiD 3 Plus System",
        "AB SOLiD 4 System",
        "AB SOLiD 4hq System",
        "AB SOLiD PI System",
        "AB 5500 Genetic Analyzer",
        "Illumina HiSeq 3500",
        "AB 5500xl Genetic Analyzer",
        "AB SOLiD System",
        "AB 3730xl",
        "454 GS FLX",
        "454 GS",
        "454 GS 20",
        "454 GS FLX+",
        "454 GS FLX Titanium",
        "454 GS Junior",
        "Complete Genomics",
        "Illumina NextSeq 500",
        "unspecified",
        "Affymetrix",
        "Illumina",
        "Ion Torrent PGM",
        "Ion Torrent Proton",
        "Illumina HiSeq X Ten",
        "Ion S5XL",
        "Ion Personal Genome Machine (PGM) System v2",
        "Ilumina NovaSeq 6000",
        "AB 3300 Genetic Analyzer",
        "Illumina HiSeq 4000",
        "Oxford Nanopore PromethION",
        "ABI PRISM 310 Genetic Analyzer",
        "Illumina Hiseq Xten",
        "Illumina MiniSeq",
        "MGISEQ-2000",
        "Illumina CanineHD",
        "Illumina HiSeq 2000",
        "Illumina HiSeq 2500",
        "Illumina HiSeq 1000",
        "Illumina HiScanSQ",
        "Illumina MiSeq",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access"
    ] = Field(..., alias="value")

    @field_validator('value', mode='before')
    def validate_platform_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v


class FAANGEVAAnalysis(BaseModel):
    """
    Pydantic model for EVA (European Variation Archive) analysis metadata.
    Based on faang_analyses_eva.metadata_rules.json
    """
    # required fields
    experiment_type: List[ExperimentTypeItem] = Field(
        ...,
        alias="experiment type",
        description="The type of experiment."
    )
    program: str = Field(
        ...,
        alias="program",
        description="The programs/tools used in the analysis separated by commas.",
        json_schema_extra={"recommended": True}
    )
    platform: List[PlatformItem] = Field(
        ...,
        alias="platform",
        description="The platform(s) used to do the sequencing separated by commas."
    )
    special_analysis_type: Optional[Literal["imputation analysis", "phasing analysis"]] = Field(
        None,
        alias="special analysis type",
        description="Indicates the special type of analysis, e.g. imputation analysis, phasing analysis."
    )

    @field_validator('experiment_type', mode='before')
    def validate_experiment_type_array(cls, v):
        if isinstance(v, list):
            # Handle list of dicts with 'value' key
            return [item if isinstance(item, dict) else {'value': item} for item in v]
        return v

    @field_validator('platform', mode='before')
    def validate_platform_array(cls, v):
        if isinstance(v, list):
            # Handle list of dicts with 'value' key
            return [item if isinstance(item, dict) else {'value': item} for item in v]
        return v

    @field_validator('program', mode='before')
    def validate_program_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v

    @field_validator('special_analysis_type', mode='before')
    def validate_special_analysis_type_value(cls, v):
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


