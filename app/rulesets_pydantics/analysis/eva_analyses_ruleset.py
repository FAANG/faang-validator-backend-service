from pydantic import Field, field_validator
from typing import List, Literal, Optional
from app.validation.validation_utils import strip_and_convert_empty_to_none
from app.rulesets_pydantics.analysis.ena_analyses_ruleset import ENAAnalysis


class EVAAnalysis(ENAAnalysis):
    # required fields
    experiment_type: List[Literal[
        "Whole Genome Sequencing",
        "Whole Transcriptome Sequencing",
        "Exome Sequencing",
        "Genotyping By Array",
        "Transcriptomics",
        "Curation",
        "Genotyping By Sequencing",
        "Target Sequencing",
        "restricted access"
    ]] = Field(
        ...,
        alias="Experiment Type")

    program: Optional[str] = Field(
        None,
        alias="Program",
        json_schema_extra={"recommended": True}
    )

    platform: Optional[List[Literal[
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
    ]]] = Field(
        None,
        alias="Platform",
        json_schema_extra={"recommended": True}
    )

    # optional
    special_analysis_type: Optional[Literal[
        "imputation analysis",
        "phasing analysis"
    ]] = Field(
        None,
        alias="Special Analysis Type")

    # validators
    @field_validator('experiment_type')
    def validate_experiment_type_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("Experiment Type is required and cannot be empty")
        return v

    @field_validator('platform', mode='before')
    def validate_platform_array(cls, v):
        if not v:
            return None

        if isinstance(v, list):
            result = [item.strip() for item in v if item and str(item).strip()]
            return result if result else None

        if isinstance(v, str) and v.strip():
            return [v.strip()]

        return None

    @field_validator('program', 'special_analysis_type', mode='before')
    def convert_empty_strings_to_none_eva(cls, v):
        return strip_and_convert_empty_to_none(v)

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"