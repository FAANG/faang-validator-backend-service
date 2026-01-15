from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Union
from app.validation.validation_utils import (
    validate_url,
    normalize_ontology_term,
    strip_and_convert_empty_to_none
)
from app.validation.generic_validator_classes import get_ontology_validator
from .core_ruleset import ExperimentCoreMetadata


class WGSExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Experiment Target")
    experiment_target_term_source_id: Literal["EFO:0005031", "restricted access"] = Field(
        ..., alias="Term Source ID")
    
    library_generation_pcr_product_isolation_protocol: str = Field(
        ..., alias="Library Generation PCR Product Isolation Protocol")
    library_generation_protocol: str = Field(..., alias="Library Generation Protocol")
    
    # optional fields
    library_selection: Optional[Literal[
        "reduced representation",
        "none"
    ]] = Field(None, alias="Library Selection")
    
    # validators
    @field_validator('experiment_target_term_source_id')
    def validate_experiment_target_term(cls, v, info):
        if v == "restricted access":
            return v

        term = normalize_ontology_term(v)
        ov = get_ontology_validator()

        res = ov.validate_ontology_term(
            term=term,
            ontology_name="EFO",
            allowed_classes=["EFO:0005031"],
            text=info.data.get('experiment_target'),
            field_name='experiment_target'
        )
        if res.errors:
            raise ValueError(f"Experiment target term invalid: {res.errors}")

        return v

    @field_validator(
        'library_generation_pcr_product_isolation_protocol',
        'library_generation_protocol'
    )
    def validate_protocol_urls(cls, v):
        return validate_url(v, field_name="Protocol", allow_restricted=True)
    
    @field_validator('library_selection', mode='before')
    def convert_empty_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
