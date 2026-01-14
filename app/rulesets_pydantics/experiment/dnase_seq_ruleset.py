from pydantic import BaseModel, Field, field_validator
from typing import Literal
from app.validation.validation_utils import (
    validate_url,
    normalize_ontology_term
)
from .core_ruleset import ExperimentCoreMetadata
from app.validation.generic_validator_classes import get_ontology_validator


class DNaseSeqExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: str = Field(..., alias="Experiment Target")
    experiment_target_term_source_id: Literal["SO:0001747", "restricted access"] = Field(..., alias="Experiment Target Term Source ID")
    
    dnase_protocol: str = Field(..., alias="Dnase Protocol")
    
    # Validators
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
    
    @field_validator('dnase_protocol')
    def validate_protocol_url(cls, v):
        return validate_url(v, field_name="DNase Protocol", allow_restricted=True)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
