from pydantic import BaseModel, Field, field_validator
from typing import Literal, Union
from app.validation.generic_validator_classes import get_ontology_validator
from app.validation.validation_utils import (
    normalize_ontology_term,
    is_restricted_value,
    validate_sample_name,
    validate_date_format,
    validate_protocol_url,
    validate_non_negative_numeric,
    validate_percentage,
    validate_url,
    strip_and_convert_empty_to_none
)

from .core_ruleset import ExperimentCoreMetadata


class ATACSeqExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: str = Field(..., alias="Experiment Target")
    experiment_target_term_source_id: Literal["SO:0001747", "restricted access"] = Field(
        ..., alias="Experiment Target Term Source ID")
    transposase_protocol: str = Field(..., alias="Transposase Protocol")
    
    # Validators
    @field_validator('experiment_target')
    def validate_target_text(cls, v):
        if v and v.strip():
            return v
        raise ValueError("Experiment target text is required")
    

    @field_validator('experiment_target_term_source_id')
    def validate_experiment_target_term(cls, v, info):
        if v == "restricted access":
            return v

        term = normalize_ontology_term(v)
        ov = get_ontology_validator()

        res = ov.validate_ontology_term(
            term=term,
            ontology_name="SO",
            allowed_classes=["SO:0001747"],
            text=info.data.get('experiment_target'),
            field_name='experiment_target'
        )
        if res.errors:
            raise ValueError(f"Experiment target term invalid: {res.errors}")

        return v
    
    @field_validator('transposase_protocol')
    def validate_transposase_protocol_url(cls, v):
        return validate_url(v, field_name="Transposase Protocol", allow_restricted=True)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
