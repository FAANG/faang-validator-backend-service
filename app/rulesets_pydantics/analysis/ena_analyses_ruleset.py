from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Literal, Optional
from app.validation.validation_utils import (
    validate_date_format,
    strip_and_convert_empty_to_none
)


class ENAAnalysis(BaseModel):
    # required fields
    alias: str = Field(..., alias="Alias")

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
        alias="Analysis Type")

    study: str = Field(
        ...,
        alias="Study"
    )

    file_names: List[str] = Field(
        ...,
        alias="File Names"
    )

    file_types: List[Literal[
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
    ]] = Field(
        ...,
        alias="File Types")

    checksum_methods: List[str] = Field(
        ...,
        alias="Checksum Methods")

    checksums: List[str] = Field(
        ...,
        alias="Checksums")

    # recommended fields
    title: Optional[str] = Field(
        None,
        alias="Title",
        json_schema_extra={"recommended": True}
    )

    description: Optional[str] = Field(
        None,
        alias="Description",
        json_schema_extra={"recommended": True}
    )

    samples: Optional[List[str]] = Field(
        None,
        alias="Samples",
        json_schema_extra={"recommended": True}
    )

    experiments: Optional[List[str]] = Field(
        None,
        alias="Experiments",
        json_schema_extra={"recommended": True}
    )

    runs: Optional[List[str]] = Field(
        None,
        alias="Runs",
        json_schema_extra={"recommended": True}
    )

    # optional fields
    related_analyses: Optional[List[str]] = Field(
        None,
        alias="Related Analyses")

    analysis_center: Optional[str] = Field(
        None,
        alias="Analysis Center")

    analysis_date: Optional[str] = Field(
        None,
        alias="Analysis Date")

    analysis_date_unit: Optional[Literal[
        "YYYY-MM-DD",
        "YYYY-MM",
        "YYYY"
    ]] = Field(
        None,
        alias="Unit")

    # validators
    @field_validator('alias', 'study')
    def validate_required_string_not_empty(cls, v, info):
        if not v or (isinstance(v, str) and v.strip() == ""):
            field_name = info.field_name
            raise ValueError(f"{field_name} is required and cannot be empty")
        return v.strip() if isinstance(v, str) else v

    @field_validator('file_names', 'file_types', 'checksum_methods', 'checksums')
    def validate_required_arrays_not_empty(cls, v, info):
        field_name = info.field_name
        if not v or len(v) == 0:
            raise ValueError(f"{field_name} is required and cannot be empty")
        return v

    @field_validator('samples', 'experiments', 'runs', 'related_analyses', mode='before')
    def validate_optional_arrays(cls, v):
        if not v:
            return None

        if isinstance(v, list):
            result = [item.strip() for item in v if item and str(item).strip()]
            return result if result else None

        if isinstance(v, str) and v.strip():
            return [v.strip()]

        return None

    @field_validator('analysis_date')
    def validate_analysis_date_format(cls, v, info):
        if not v:
            return None

        values = info.data
        unit = values.get('Unit') or values.get('analysis_date_unit')
        return validate_date_format(v, unit, "Analysis date")

    @field_validator(
        'title', 'description', 'analysis_center', 'analysis_date_unit',
        mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

    @model_validator(mode='after')
    def validate_file_arrays_same_length(self):
        arrays = {
            'file_names': len(self.file_names) if self.file_names else 0,
            'file_types': len(self.file_types) if self.file_types else 0,
            'checksum_methods': len(self.checksum_methods) if self.checksum_methods else 0,
            'checksums': len(self.checksums) if self.checksums else 0
        }

        lengths = set(arrays.values())
        if len(lengths) > 1:
            raise ValueError(
                f"File Names, File Types, Checksum Methods, and Checksums must all have the same length. "
                f"Got: File Names={arrays['file_names']}, File Types={arrays['file_types']}, "
                f"Checksum Methods={arrays['checksum_methods']}, Checksums={arrays['checksums']}"
            )

        return self

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"