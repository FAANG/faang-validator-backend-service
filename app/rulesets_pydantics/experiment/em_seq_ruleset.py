from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Union
from app.validation.validation_utils import (
    validate_url,
    validate_non_negative_numeric,
    strip_and_convert_empty_to_none,
normalize_ontology_term
)
from .core_ruleset import ExperimentCoreMetadata
from app.validation.generic_validator_classes import get_ontology_validator


class EMSeqExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: str = Field(..., alias="Experiment Target")
    experiment_target_term_source_id: Literal["GO:0006306", "restricted access"] = Field(..., alias="Term Source ID")
    
    library_selection: Literal[
        "whole-genome",
        "selected genomic regions",
        "restricted access"
    ] = Field(..., alias="Library Selection")
    
    max_fragment_size_selection_range: Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]] = Field(..., alias="Max Fragment Size Selection Range") # tocheck - might be recommended
    
    min_fragment_size_selection_range: Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]] = Field(..., alias="Min Fragment Size Selection Range") # tocheck - might be recommended
    
    enzymatic_methylation_conversion_protocol: str = Field(..., alias="Enzymatic Methylation Conversion Protocol")
    
    # recommended fields
    enzymatic_methylation_conversion_percent: Optional[Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="Enzymatic Methylation Conversion Percent",
                json_schema_extra={"recommended": True})
    
    # validators
    @field_validator('experiment_target_term_source_id')
    def validate_experiment_target_term(cls, v, info):
        if v == "restricted access":
            return v

        term = normalize_ontology_term(v)
        ov = get_ontology_validator()

        res = ov.validate_ontology_term(
            term=term,
            ontology_name="OBI",
            allowed_classes=["GO:0006306"],
            text=info.data.get('experiment_target'),
            field_name='experiment_target'
        )
        if res.errors:
            raise ValueError(f"Experiment target term invalid: {res.errors}")

        return v

    @field_validator('enzymatic_methylation_conversion_protocol')
    def validate_protocol_url(cls, v):
        return validate_url(v, field_name="Enzymatic Methylation Conversion Protocol", allow_restricted=True)
    
    @field_validator('max_fragment_size_selection_range', 'min_fragment_size_selection_range', mode='before')
    def validate_fragment_size(cls, v):
        if v in ["not applicable", "not collected", "not provided", "restricted access"]:
            return v
        return validate_non_negative_numeric(v, "Fragment size", allow_restricted=False)
    
    @field_validator('enzymatic_methylation_conversion_percent', mode='before')
    def validate_conversion_percent(cls, v):
        if v in ["not applicable", "not collected", "not provided", "restricted access", None]:
            return v
        try:
            val = float(v)
            if val < 0 or val > 100:
                raise ValueError("Enzymatic methylation conversion percent must be between 0 and 100")
            return val
        except (ValueError, TypeError):
            return None
    
    @field_validator('enzymatic_methylation_conversion_percent', mode='before')
    def convert_empty_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
