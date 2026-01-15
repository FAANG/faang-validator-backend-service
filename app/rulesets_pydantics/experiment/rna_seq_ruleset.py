from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Union
from app.validation.validation_utils import (
    validate_url,
    strip_and_convert_empty_to_none
)
from app.validation.generic_validator_classes import get_ontology_validator
from app.validation.validation_utils import normalize_ontology_term
from .core_ruleset import ExperimentCoreMetadata


class RNASeqExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Experiment Target")
    experiment_target_term_source_id: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Term Source ID")
    
    rna_preparation_3_adapter_ligation_protocol: str = Field(
        ..., alias="Rna Preparation 3' adapter ligation protocol")
    rna_preparation_5_adapter_ligation_protocol: str = Field(
        ..., alias="Rna Preparation 5' adapter ligation protocol")
    library_generation_pcr_product_isolation_protocol: str = Field(
        ..., alias="Library Generation PCR Product Isolation Protocol")
    preparation_reverse_transcription_protocol: str = Field(
        ..., alias="Preparation Reverse Transcription Protocol")
    library_generation_protocol: str = Field(
        ..., alias="Library Generation Protocol")
    
    read_strand: Literal[
        "not applicable",
        "sense",
        "antisense",
        "mate 1 sense",
        "mate 2 sense",
        "non-stranded",
        "restricted access"
    ] = Field(..., alias="Read Strand")
    
    # recommended fields
    rna_purity_260_280_ratio: Optional[Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="RNA Purity 260-280 ratio",
                json_schema_extra={"recommended": True})
    
    rna_purity_260_230_ratio: Optional[Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="RNA Purity 260-230 ratio",
                json_schema_extra={"recommended": True})
    
    rna_integrity_number: Optional[Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="RNA Integrity Number",
                json_schema_extra={"recommended": True})
    
    # Validators
    @field_validator('experiment_target_term_source_id')
    def validate_target_term(cls, v, info):
        if v == "restricted access":
            return v

        term = normalize_ontology_term(v)
        
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name="EFO",
            allowed_classes=["CHEBI:33697"],
            text=info.data.get('experiment_target'),
            field_name='experiment_target'
        )
        if res.errors:
            raise ValueError(f"Experiment target term invalid: {res.errors}")
        
        return v
    
    @field_validator(
        'rna_preparation_3_adapter_ligation_protocol',
        'rna_preparation_5_adapter_ligation_protocol',
        'library_generation_pcr_product_isolation_protocol',
        'preparation_reverse_transcription_protocol',
        'library_generation_protocol'
    )
    def validate_protocol_urls(cls, v):
        return validate_url(v, field_name="Protocol", allow_restricted=True)
    
    @field_validator('rna_purity_260_280_ratio', 'rna_purity_260_230_ratio', 'rna_integrity_number', mode='before')
    def validate_rna_quality_metrics(cls, v):
        if v in ["not applicable", "not collected", "not provided", "restricted access", None]:
            return v
        try:
            return float(v)
        except (ValueError, TypeError):
            return None
    
    @field_validator(
        'rna_purity_260_280_ratio', 'rna_purity_260_230_ratio', 'rna_integrity_number',
        mode='before'
    )
    def convert_empty_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
