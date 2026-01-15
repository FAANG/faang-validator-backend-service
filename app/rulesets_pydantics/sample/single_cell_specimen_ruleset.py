from pydantic import BaseModel, Field, field_validator
from app.validation.generic_validator_classes import get_ontology_validator
from app.validation.validation_utils import (
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


class FAANGSingleCellSpecimenSample(SampleCoreMetadata):
    # required fields
    sample_name: str = Field(..., alias="Sample Name")

    tissue_dissociation: Literal[
        "proteolysis",
        "mesh passage",
        "fine needle trituration",
        "fluids",
        "mechanical dissociation"
    ] = Field(..., alias="Tissue Dissociation")

    cell_enrichment: Literal[
        "fluorescence-activated cell sorting (FACS)",
        "centrifugation",
        "magnetic levitation",
        "bead-based sorting",
        "Raman-spectometry sorting",
        "cell culture"
    ] = Field(..., alias="Cell Enrichment")

    cell_type: List[CellType] = Field(..., alias="Cell Type")

    single_cell_isolation_protocol: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Single Cell Isolation Protocol"
    )

    derived_from: List[str] = Field(..., alias="Derived From")

    # recommended fields
    enrichment_markers: Optional[Literal[
        "CD45+", "CD8+", "CD4+", "CD14+", "KRT8+", "KRT18+",
        "CD68+", "CD79A+", "CD79B+"
    ]] = Field(None, alias="Enrichment Markers", json_schema_extra={"recommended": True})

    single_cell_isolation: Optional[Literal[
        "FACS",
        "microfluidics",
        "manual selection",
        "droplet-based cell isolation"
    ]] = Field(None, alias="Single Cell Isolation", json_schema_extra={"recommended": True})

    single_cell_entity: Optional[Literal[
        "whole cell",
        "nucleus",
        "cell-cell multimer",
        "spatially encoded cell barcoding"
    ]] = Field(None, alias="Single Cell Entity", json_schema_extra={"recommended": True})

    single_cell_quality: Optional[Literal[
        "visual inspection",
        "viability metrics",
        "not done"
    ]] = Field(None, alias="Single Cell Quality", json_schema_extra={"recommended": True})

    cell_number: Optional[float] = Field(
        None, alias="Cell Number", json_schema_extra={"recommended": True}
    )
    cell_number_unit: Optional[Literal["cells"]] = Field(
        "cells", alias="Unit", json_schema_extra={"recommended": True}
    )

    @field_validator('sample_name')
    def validate_sample_name_field(cls, v):
        return validate_sample_name(v)

    @field_validator('single_cell_isolation_protocol')
    def validate_protocol_url_field(cls, v):
        return validate_protocol_url(v, allow_restricted=True)

    @field_validator('cell_number', mode='before')
    def validate_cell_number_value(cls, v):
        return validate_non_negative_numeric(v, "Cell number", allow_restricted=False)

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
            raise ValueError("Single cell specimen must be derived from exactly one specimen")
        return v

    # convert empty strings to None for optional fields
    @field_validator(
        'enrichment_markers', 'single_cell_isolation', 'single_cell_entity',
        'single_cell_quality', 'cell_number', 'cell_number_unit',
        'availability', 'same_as', mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"