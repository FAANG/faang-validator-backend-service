from pydantic import BaseModel, Field, field_validator
from app.validations.generic_validator_classes import get_ontology_validator
from app.validations.validation_utils import (
    normalize_ontology_term,
    is_restricted_value,
    validate_sample_name,
    validate_protocol_url,
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


class FAANGCellSpecimenSample(SampleCoreMetadata):
    # required fields
    sample_name: str = Field(..., alias="Sample Name")

    cell_type: List[CellType] = Field(..., alias="Cell Type")

    purification_protocol: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Purification Protocol"
    )

    derived_from: List[str] = Field(..., alias="Derived From")

    # optional fields
    markers: Optional[str] = Field(None, alias="Markers")

    # validators
    @field_validator('sample_name')
    def validate_sample_name_field(cls, v):
        return validate_sample_name(v)

    @field_validator('purification_protocol')
    def validate_protocol_url_field(cls, v):
        return validate_protocol_url(v, allow_restricted=True)

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
            raise ValueError("Cell specimen must be derived from exactly one specimen")
        return v

    # convert empty strings to None for optional fields
    @field_validator(
        'markers', 'secondary_project', 'availability', 'same_as', mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"