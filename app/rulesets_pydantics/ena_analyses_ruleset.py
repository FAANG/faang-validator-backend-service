from pydantic import BaseModel, Field, field_validator
from typing import List, Union, Literal, Optional
from app.validations.validation_utils import (
    validate_date_format,
    strip_and_convert_empty_to_none
)


class StringValueItem(BaseModel):
    """Model for array items with string value."""
    value: str = Field(..., alias="value")

    @field_validator('value', mode='before')
    def validate_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v


class FileTypeItem(BaseModel):
    """Model for file type item in array."""
    value: Literal[
        "tab",
        "bam",
        "bed",
        "gff",
        "fasta",
        "fastq",
        "flatfile",
        "chromosome_list",
        "sample_list",
        "readme_file",
        "phenotype_file",
        "BioNano_native",
        "bai",
        "Kallisto_native",
        "agp",
        "unlocalised_list",
        "info",
        "manifest",
        "other",
        "cram",
        "crai",
        "vcf",
        "vcf_aggregate",
        "bcf",
        "tabix",
        "wig",
        "restricted access"
    ] = Field(..., alias="value")

    @field_validator('value', mode='before')
    def validate_file_type_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v


class AnalysisDate(BaseModel):
    """Model for analysis date with value and units."""
    value: str = Field(..., alias="value")
    units: Literal["YYYY-MM-DD", "YYYY-MM", "YYYY"] = Field(..., alias="units")

    @field_validator('value')
    def validate_date_format(cls, v):
        return validate_date_format(v)


class FAANGENAAnalysis(BaseModel):
    """
    Pydantic model for ENA (European Nucleotide Archive) analysis metadata.
    Based on faang_analyses_ena.metadata_rules.json
    """
    # required fields
    alias: str = Field(
        ...,
        alias="alias",
        description="The alias of the analysis."
    )
    analysis_type: Literal[
        "REFERENCE_ALIGNMENT",
        "SEQUENCE_VARIATION",
        "PATHOGEN_ANALYSIS",
        "TRANSCRIPTOME_ASSEMBLY",
        "TAXONOMIC_REFERENCE_SET",
        "SEQUENCE_ASSEMBLY",
        "SEQUENCE_FLATFILE",
        "SEQUENCE_ANNOTATION",
        "REFERENCE_SEQUENCE",
        "SAMPLE_PHENOTYPE",
        "PROCESSED_READS",
        "GENOME_MAP",
        "AMR_ANTIBIOGRAM",
        "restricted access"
    ] = Field(
        ...,
        alias="analysis type",
        description="The type of analysis performed."
    )
    study: str = Field(
        ...,
        alias="study",
        description="Identifies the parent study."
    )
    file_names: List[StringValueItem] = Field(
        ...,
        alias="file names",
        description="The names of the files associated with this analysis."
    )
    file_types: List[FileTypeItem] = Field(
        ...,
        alias="file types",
        description="The types of the files associated with this analysis."
    )
    checksum_methods: List[StringValueItem] = Field(
        ...,
        alias="checksum methods",
        description="The checksum methods used on the files."
    )
    checksums: List[StringValueItem] = Field(
        ...,
        alias="checksums",
        description="The checksum values of the files."
    )

    # recommended fields
    title: Optional[str] = Field(
        None,
        alias="title",
        description="The title of the analysis.",
        json_schema_extra={"recommended": True}
    )
    description: Optional[str] = Field(
        None,
        alias="description",
        description="Describes the analysis in detail.",
        json_schema_extra={"recommended": True}
    )
    samples: Optional[List[StringValueItem]] = Field(
        None,
        alias="samples",
        description="One or more samples associated with the analysis."
    )
    experiments: Optional[List[StringValueItem]] = Field(
        None,
        alias="experiments",
        description="One or more experiments associated with the analysis."
    )
    runs: Optional[List[StringValueItem]] = Field(
        None,
        alias="runs",
        description="One or more runs associated with the analysis."
    )
    related_analyses: Optional[List[StringValueItem]] = Field(
        None,
        alias="related analyses",
        description="One or more analyses associated with the analysis."
    )
    analysis_center: Optional[str] = Field(
        None,
        alias="analysis center",
        description="The center name of the institution responsible for this analysis."
    )
    analysis_date: Optional[AnalysisDate] = Field(
        None,
        alias="analysis date",
        description="The date when this analysis was produced."
    )

    @field_validator('alias', 'analysis_type', 'study', mode='before')
    def validate_object_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v

    @field_validator('title', 'description', 'analysis_center', mode='before')
    def validate_optional_object_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        if not v or v == "":
            return None
        return v

    @field_validator('file_names', 'file_types', 'checksum_methods', 'checksums', mode='before')
    def validate_array_items(cls, v):
        if isinstance(v, list):
            return [item if isinstance(item, dict) else {'value': item} for item in v]
        return v

    @field_validator('samples', 'experiments', 'runs', 'related_analyses', mode='before')
    def validate_optional_array_items(cls, v):
        if isinstance(v, list):
            return [item if isinstance(item, dict) else {'value': item} for item in v]
        if not v:
            return None
        return v

    @field_validator('analysis_date', mode='before')
    def validate_analysis_date(cls, v):
        if isinstance(v, dict):
            if 'value' in v and 'units' in v:
                return v
            # If it's a flat dict, try to extract
            return v
        if not v:
            return None
        return v

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"


