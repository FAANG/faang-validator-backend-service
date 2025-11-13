from pydantic import BaseModel, Field, field_validator
from app.validations.generic_validator_classes import get_ontology_validator
from app.validations.validation_utils import (
    normalize_ontology_term,
    is_restricted_value,
    validate_sample_name,
    validate_protocol_url,
    validate_non_negative_numeric,
    strip_and_convert_empty_to_none
)
from typing import List, Optional, Union, Literal
from .standard_ruleset import SampleCoreMetadata

class CellType(BaseModel):
    text: str
    term: Union[str, Literal["restricted access"]]

    @field_validator('term')
    def validate_cell_type_term(cls, v, info):
        if is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if not term.startswith("CL:"):
            raise ValueError(f"Cell type term '{v}' should be from CL ontology")

        # ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name="CL",
            allowed_classes=["CL:0000000"],
            text=info.data.get('text'),
            field_name='cell_type'
        )
        if res.errors:
            raise ValueError(f"Cell type term invalid: {res.errors}")

        return v

class FAANGCellCultureSample(SampleCoreMetadata):
    # required fields
    sample_name: str = Field(..., alias="Sample Name")

    culture_type: str = Field(..., alias="Culture Type")
    culture_type_term_source_id: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Culture Type Term Source ID"
    )

    cell_type: List[CellType] = Field(..., alias="Cell Type")

    cell_culture_protocol: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Cell Culture Protocol"
    )

    culture_conditions: str = Field(..., alias="Culture Conditions")

    number_of_passages: Union[float, Literal["restricted access"]] = Field(
        ..., alias="Number Of Passages"
    )

    derived_from: List[str] = Field(..., alias="Derived From")

    # validators
    @field_validator('sample_name')
    def validate_sample_name_field(cls, v):
        return validate_sample_name(v)

    @field_validator('culture_type_term_source_id')
    def validate_culture_type_term(cls, v, info):
        if is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if not term.startswith("BTO:"):
            raise ValueError(f"Culture type term '{v}' should be from BTO ontology")

        # ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name="BTO",
            allowed_classes=["BTO:0000214"],
            text=info.data.get('culture_type'),
            field_name='culture_type'
        )
        if res.errors:
            raise ValueError(f"Culture type term invalid: {res.errors}")

        return v



    @field_validator('cell_culture_protocol')
    def validate_protocol_url_field(cls, v):
        return validate_protocol_url(v, allow_restricted=True)

    @field_validator('culture_conditions')
    def validate_culture_conditions_field(cls, v):
        if not v or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Culture conditions is required and cannot be empty")
        return v.strip() if isinstance(v, str) else v

    @field_validator('number_of_passages', mode='before')
    def validate_number_of_passages_value(cls, v):
        if v == "restricted access":
            return v

        if v is None or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Number of passages is required")

        return validate_non_negative_numeric(v, "Number of passages", allow_restricted=True)

    @field_validator('derived_from', mode='before')
    def normalize_derived_from(cls, v):
        if v is None:
            raise ValueError("Derived from is required")

        if isinstance(v, str):
            if not v.strip():
                raise ValueError("Derived from value is required and cannot be empty")
            return [v.strip()]

        if isinstance(v, list):
            non_empty = [item.strip() for item in v if item and str(item).strip()]
            if not non_empty:
                raise ValueError("Derived from is required and cannot be empty")
            return non_empty

        raise ValueError("Derived from must be a string or list of strings")

    @field_validator('derived_from')
    def validate_single_parent(cls, v):
        if len(v) != 1:
            raise ValueError("Cell culture must be derived from exactly one specimen")
        return v

    @field_validator('cell_type')
    def validate_single_cell_type(cls, v):
        if len(v) != 1:
            raise ValueError("Cell culture must have exactly one cell type")
        return v

    # convert empty strings to None for optional fields
    @field_validator(
        'secondary_project', 'availability', 'same_as', mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"