from pydantic import BaseModel, Field, field_validator
from app.validation.generic_validator_classes import get_ontology_validator
from typing import Optional, Literal, Union
from app.validation.validation_utils import (
    validate_url,
    normalize_ontology_term,
    validate_non_negative_numeric,
    strip_and_convert_empty_to_none
)
from .core_ruleset import ExperimentCoreMetadata


class BSSeqExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: str = Field(..., alias="Experiment Target")
    experiment_target_term_source_id: Literal["GO:0006306", "restricted access"] = Field(
        ..., alias="Term Source ID")
    library_selection: Literal["RRBS", "WGBS", "restricted access"] = Field(
        ..., alias="Library Selection")
    bisulfite_conversion_protocol: str = Field(..., alias="Bisulfite Conversion Protocol")
    pcr_product_isolation_protocol: str = Field(..., alias="PCR Product Isolation Protocol")
    bisulfite_conversion_percent: Union[float, Literal["restricted access"]] = Field(
        ..., alias="Bisulfite Conversion Percent")
    
    # recommended fields
    restriction_enzyme: Optional[str] = Field(
        None, alias="Restriction Enzyme",
        json_schema_extra={"recommended": True})
    
    max_fragment_size_selection_range: Optional[Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="Max Fragment Size Selection Range",
                json_schema_extra={"recommended": True})
    
    min_fragment_size_selection_range: Optional[Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="Min Fragment Size Selection Range",
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
    
    @field_validator('bisulfite_conversion_protocol', 'pcr_product_isolation_protocol')
    def validate_protocol_urls(cls, v):
        return validate_url(v, field_name="Protocol", allow_restricted=True)
    
    @field_validator('bisulfite_conversion_percent', mode='before')
    def validate_conversion_percent(cls, v):
        if v == "restricted access":
            return v
        try:
            val = float(v)
            if val < 0 or val > 100:
                raise ValueError("Bisulfite conversion percent must be between 0 and 100")
            return val
        except (ValueError, TypeError):
            raise ValueError("Bisulfite conversion percent must be a number or 'restricted access'")
    
    @field_validator('max_fragment_size_selection_range', 'min_fragment_size_selection_range', mode='before')
    def validate_fragment_size(cls, v):
        if v in ["not applicable", "not collected", "not provided", "restricted access", None, ""]:
            return v
        return validate_non_negative_numeric(v, "Fragment size", allow_restricted=False)
    
    @field_validator(
        'restriction_enzyme', 'max_fragment_size_selection_range', 'min_fragment_size_selection_range',
        mode='before'
    )
    def convert_empty_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
