from pydantic import BaseModel, Field, field_validator, model_validator
from app.validations.generic_validator_classes import get_ontology_validator
from app.validations.validation_utils import (
    normalize_ontology_term,
    is_restricted_value,
    validate_sample_name,
    validate_date_format,
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

        if not term.startswith("CL:") and not term.startswith("BTO:"):
            raise ValueError(f"Cell type term '{v}' should be from CL or BTO ontology")

        if term.startswith("CL:"):
            ontology_name = "CL"
            allowed_classes = ["CL:0000000"]
        else:
            ontology_name = "BTO"
            allowed_classes = ["BTO:0000000"]

        # Ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=allowed_classes,
            text=info.data.get('text'),
            field_name='cell_type'
        )
        if res.errors:
            raise ValueError(f"Cell type term invalid: {res.errors}")

        return v


class FAANGCellLineSample(SampleCoreMetadata):
    # required fields
    sample_name: str = Field(..., alias="Sample Name")

    organism: str = Field(..., alias="Organism")
    organism_term_source_id: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Organism Term Source ID"
    )

    sex: str = Field(..., alias="Sex")
    sex_term_source_id: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Sex Term Source ID"
    )

    cell_line: str = Field(..., alias="Cell Line")
    biomaterial_provider: str = Field(..., alias="Biomaterial Provider")

    # recommended fields
    catalogue_number: Optional[str] = Field(
        None, alias="Catalogue Number", json_schema_extra={"recommended": True}
    )

    number_of_passages: Optional[Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="Number of Passages", json_schema_extra={"recommended": True})

    date_established: Optional[Union[str, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="Date Established", json_schema_extra={"recommended": True})

    date_established_unit: Optional[Literal[
        "YYYY-MM-DD", "YYYY-MM", "YYYY",
        "not applicable", "not collected", "not provided", "restricted access"
    ]] = Field(None, alias="Unit", json_schema_extra={"recommended": True})

    publication: Optional[str] = Field(
        None, alias="Publication", json_schema_extra={"recommended": True}
    )

    # optional fields
    breed: Optional[str] = Field(None, alias="Breed")
    breed_term_source_id: Optional[Union[str, Literal["restricted access"]]] = Field(
        None, alias="Breed Term Source ID"
    )

    cell_type: Optional[List[CellType]] = Field(None, alias="Cell Type")

    culture_conditions: Optional[str] = Field(None, alias="Culture Conditions")
    culture_protocol: Optional[str] = Field(None, alias="Culture Protocol")

    disease: Optional[str] = Field(None, alias="Disease")
    disease_term_source_id: Optional[Union[str, Literal["restricted access"]]] = Field(
        None, alias="Disease Term Source ID"
    )

    karyotype: Optional[str] = Field(None, alias="Karyotype")
    derived_from: Optional[Union[str, List[str]]] = Field(None, alias="Derived From")

    # validators
    @field_validator('sample_name')
    def validate_sample_name_field(cls, v):
        return validate_sample_name(v)

    @field_validator('organism_term_source_id')
    def validate_organism_term(cls, v, info):
        if is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if not term.startswith("NCBITaxon:"):
            raise ValueError(f"Organism term '{v}' should be from NCBITaxon ontology")

        # Ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name="NCBITaxon",
            allowed_classes=["NCBITaxon:1"],
            text=info.data.get('organism'),
            field_name='organism'
        )
        if res.errors:
            raise ValueError(f"Organism term invalid: {res.errors}")

        return v

    @field_validator('sex_term_source_id')
    def validate_sex_term(cls, v, info):
        if is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if not term.startswith("PATO:"):
            raise ValueError(f"Sex term '{v}' should be from PATO ontology")

        # Ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name="PATO",
            allowed_classes=["PATO:0000047"],
            text=info.data.get('sex'),
            field_name='sex'
        )
        if res.errors:
            raise ValueError(f"Sex term invalid: {res.errors}")

        return v

    @field_validator('breed_term_source_id')
    def validate_breed_term(cls, v, info):
        if not v or is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if not term.startswith("LBO:"):
            raise ValueError(f"Breed term '{v}' should be from LBO ontology")

        # Ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name="LBO",
            allowed_classes=["LBO:0000000"],
            text=info.data.get('breed'),
            field_name='breed'
        )
        if res.errors:
            raise ValueError(f"Breed term invalid: {res.errors}")

        return v

    @field_validator('disease_term_source_id')
    def validate_disease_term(cls, v, info):
        if not v or is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if not term.startswith("PATO:") and not term.startswith("EFO:"):
            raise ValueError(f"Disease term '{v}' should be from PATO or EFO ontology")

        if term.startswith("PATO:"):
            ontology_name = "PATO"
            allowed_classes = ["PATO:0000461"]
        else:
            ontology_name = "EFO"
            allowed_classes = ["EFO:0000408"]

        # Ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=allowed_classes,
            text=info.data.get('disease'),
            field_name='disease'
        )
        if res.errors:
            raise ValueError(f"Disease term invalid: {res.errors}")

        return v

    @field_validator('cell_line')
    def validate_cell_line_field(cls, v):
        if not v or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Cell line is required and cannot be empty")
        return v.strip() if isinstance(v, str) else v

    @field_validator('biomaterial_provider')
    def validate_biomaterial_provider_field(cls, v):
        if not v or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Biomaterial provider is required and cannot be empty")
        return v.strip() if isinstance(v, str) else v

    @field_validator('number_of_passages', mode='before')
    def validate_number_of_passages_value(cls, v):
        if v is None or v == "":
            return None

        # Allow special missing values
        special_values = ["not applicable", "not collected", "not provided", "restricted access"]
        if v in special_values:
            return v

        try:
            numeric_val = float(v)
            if numeric_val < 0:
                raise ValueError(f"Number of passages must be non-negative, got {numeric_val}")
            return numeric_val
        except ValueError as e:
            if "non-negative" in str(e):
                raise
            raise ValueError(f"Number of passages must be a valid number or special missing value, got '{v}'")

    @field_validator('date_established')
    def validate_date_established_format(cls, v, info):
        if not v or is_restricted_value(v):
            return v

        # Strip timestamp if present
        if ' ' in str(v):
            v = str(v).split(' ')[0]

        values = info.data
        unit = values.get('Unit') or values.get('date_established_unit')
        return validate_date_format(v, unit, "Date established")

    @field_validator('culture_protocol')
    def validate_protocol_url_field(cls, v):
        if not v:
            return v
        return validate_protocol_url(v, allow_restricted=False)

    @field_validator('derived_from', mode='before')
    def normalize_derived_from(cls, v):
        # Derived from is optional for cell line
        if v is None or v == "":
            return None

        if isinstance(v, str):
            if not v.strip():
                return None
            return [v.strip()]

        if isinstance(v, list):
            non_empty = [item.strip() for item in v if item and str(item).strip()]
            return non_empty if non_empty else None

        return None

    @field_validator('derived_from')
    def validate_derived_from_optional(cls, v):
        # If provided, should be exactly one
        if v is not None and len(v) != 1:
            raise ValueError("Cell line can be derived from at most one specimen")
        return v

    # Convert empty strings to None for optional fields
    @field_validator(
        'catalogue_number', 'number_of_passages', 'date_established', 'date_established_unit',
        'publication', 'breed', 'breed_term_source_id', 'cell_type',
        'culture_conditions', 'culture_protocol', 'disease', 'disease_term_source_id',
        'karyotype', 'secondary_project', 'availability', 'same_as', mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

    @model_validator(mode='after')
    def validate_consistency(self):
        # Breed consistency
        if self.breed and not self.breed_term_source_id:
            raise ValueError("Breed term source ID is required when breed text is provided")
        if (self.breed_term_source_id and
            self.breed_term_source_id not in ["", "restricted access"] and
            (not self.breed or not self.breed.strip())):
            raise ValueError("Breed text is required when breed term source ID is provided")

        # Disease consistency
        if self.disease and not self.disease_term_source_id:
            raise ValueError("Disease term source ID is required when disease text is provided")
        if (self.disease_term_source_id and
            self.disease_term_source_id not in ["", "restricted access"] and
            (not self.disease or not self.disease.strip())):
            raise ValueError("Disease text is required when disease term source ID is provided")

        return self

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"