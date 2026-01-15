from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Union
from app.validation.validation_utils import (
    validate_url,
    validate_non_negative_numeric,
    strip_and_convert_empty_to_none
)
from app.validation.generic_validator_classes import get_ontology_validator
from app.validation.validation_utils import normalize_ontology_term
from .core_ruleset import ExperimentCoreMetadata


class scRNASeqExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Experiment Target")
    experiment_target_term_source_id: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Term Source ID")
    
    library_construction: Literal[
        "Smart-Seq2",
        "Drop-Seq",
        "10X v1",
        "10X v2",
        "10X v3"
    ] = Field(..., alias="Library Construction")
    
    end_bias: Literal[
        "3 prime tag",
        "5 prime tag",
        "full-length",
        "none",
        "restricted access"
    ] = Field(..., alias="End Bias")
    
    library_strand: Literal[
        "first (antisense)",
        "second (sense)",
        "both",
        "restricted access"
    ] = Field(..., alias="Library Strand")
    
    library_generation_protocol: str = Field(..., alias="Library Generation Protocol")
    sequencing_protocol: str = Field(..., alias="Sequencing Protocol")
    
    read_strand: Literal[
        "sense",
        "antisense",
        "mate 1 sense",
        "mate 2 sense",
        "non-stranded",
        "restricted access"
    ] = Field(..., alias="Read Strand")
    
    # recommended fields
    primer: Optional[Literal["oligo-dT", "random"]] = Field(
        None, alias="Primer",
        json_schema_extra={"recommended": True})
    
    spike_in: Optional[Literal[
        "none",
        "External RNA Controls Consortium (ERCC)",
        "restricted access"
    ]] = Field(None, alias="Spike In",
               json_schema_extra={"recommended": True})
    
    spike_in_dilution_or_concentration: Optional[Literal[
        "1:40,000",
        "restricted access"
    ]] = Field(None, alias="Spike In Dilution or Concentration", json_schema_extra={"recommended": True})
    
    # optional fields
    amplification_method: Optional[Literal[
        "PCR",
        "in vitro transcription",
        "not collected",
        "not provided",
        "restricted access"
    ]] = Field(None, alias="Amplification Method")
    
    amplification_cycles: Optional[Union[float, Literal[
        "not collected",
        "not provided",
        "restricted access"
    ]]] = Field(None, alias="Amplification Cycles")
    
    rna_purity_260_280_ratio: Optional[Union[float, Literal[
        "not collected",
        "not provided",
        "restricted access"
    ]]] = Field(None, alias="RNA Purity 260-280 Ratio")
    
    rna_purity_260_230_ratio: Optional[Union[float, Literal[
        "not collected",
        "not provided",
        "restricted access"
    ]]] = Field(None, alias="RNA Purity 260-230 Ratio")
    
    rna_integrity_number: Optional[Union[float, Literal[
        "not collected",
        "not provided",
        "restricted access"
    ]]] = Field(None, alias="RNA Integrity Number")
    
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
    
    @field_validator('library_generation_protocol', 'sequencing_protocol')
    def validate_protocol_urls(cls, v):
        return validate_url(v, field_name="Protocol", allow_restricted=True)
    
    @field_validator('amplification_cycles', mode='before')
    def validate_amplification_cycles(cls, v):
        if v in ["not collected", "not provided", "restricted access", None]:
            return v
        return validate_non_negative_numeric(v, "Amplification cycles", allow_restricted=False)
    
    @field_validator(
        'rna_purity_260_280_ratio', 'rna_purity_260_230_ratio',
        'rna_integrity_number', mode='before'
    )
    def validate_rna_quality_metrics(cls, v):
        if v in ["not collected", "not provided", "restricted access", None]:
            return v
        try:
            return float(v)
        except (ValueError, TypeError):
            return None
    
    @field_validator(
        'primer', 'spike_in', 'spike_in_dilution_or_concentration',
        'amplification_method', 'amplification_cycles',
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
