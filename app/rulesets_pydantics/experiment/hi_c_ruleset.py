from pydantic import BaseModel, Field, field_validator
from typing import Literal
from app.validation.validation_utils import (
    validate_url,
    normalize_ontology_term
)
from .core_ruleset import ExperimentCoreMetadata
from app.validation.generic_validator_classes import get_ontology_validator


class HiCExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: str = Field(..., alias="Experiment Target")
    experiment_target_term_source_id: Literal["GO:0000785", "restricted access"] = Field(
        ..., alias="Term Source ID")
    restriction_enzyme: str = Field(..., alias="Restriction Enzyme")
    restriction_site: str = Field(..., alias="Restriction Site")
    hi_c_protocol: str = Field(..., alias="Hi-C Protocol")
    
    # validators
    @field_validator('experiment_target_term_source_id')
    def validate_experiment_target_term(cls, v, info):
        if v == "restricted access":
            return v

        term = normalize_ontology_term(v)
        ov = get_ontology_validator()

        res = ov.validate_ontology_term(
            term=term,
            ontology_name="GO",
            allowed_classes=["GO:0000785"],
            text=info.data.get('experiment_target'),
            field_name='experiment_target'
        )
        if res.errors:
            raise ValueError(f"Experiment target term invalid: {res.errors}")

        return v

    @field_validator('hi_c_protocol')
    def validate_protocol_url(cls, v):
        return validate_url(v, field_name="Hi-C Protocol", allow_restricted=True)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
