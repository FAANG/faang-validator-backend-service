from pydantic import Field, field_validator, model_validator
from app.validations.generic_validator_classes import OntologyValidator
from typing import Optional, Union, Literal
import re
from datetime import datetime

from .standard_ruleset import SampleCoreMetadata


class FAANGOrganoidSample(SampleCoreMetadata):
    # required fields
    sample_name: str = Field(..., alias="Sample Name")
    organ_model: str = Field(..., alias="Organ Model")
    organ_model_term_source_id: Union[str, Literal["restricted access"]] = Field(...,
                                                                                 alias="Organ Model Term Source ID")
    freezing_method: Literal[
        "ambient temperature", "cut slide", "fresh", "frozen, -70 freezer",
        "frozen, -150 freezer", "frozen, liquid nitrogen", "frozen, vapor phase",
        "paraffin block", "RNAlater, frozen", "TRIzol, frozen"
    ] = Field(..., alias="Freezing Method")

    organoid_passage: float = Field(..., alias="Organoid Passage")
    organoid_passage_unit: Literal["passages"] = Field("passages", alias="Organoid Passage Unit")
    organoid_passage_protocol: Union[str, Literal["restricted access"]] = Field(..., alias="Organoid Passage Protocol")

    type_of_organoid_culture: Literal["2D", "3D"] = Field(..., alias="Type Of Organoid Culture")
    growth_environment: Literal["matrigel", "liquid suspension", "adherent"] = Field(..., alias="Growth Environment")
    growth_environment_unit: Optional[str] = Field(None, alias="Growth Environment Unit")
    derived_from: str = Field(..., alias="Derived From")

    # Optional fields
    organ_part_model: Optional[str] = Field(None, alias="Organ Part Model")
    organ_part_model_term_source_id: Optional[Union[str, Literal["restricted access"]]] = Field(None,
                                                                                                alias="Organ Part Model Term Source ID")
    number_of_frozen_cells: Optional[float] = Field(None, alias="Number Of Frozen Cells")
    number_of_frozen_cells_unit: Optional[Literal["organoids"]] = Field("organoids", alias="Number Of Frozen Cells Unit")
    organoid_culture_and_passage_protocol: Optional[Union[str, Literal["restricted access"]]] = Field(None,
                                                                                                      alias="Organoid Culture And Passage Protocol")
    organoid_morphology: Optional[str] = Field(None, alias="Organoid Morphology")

    stored_oxygen_level: Optional[str] = Field(None, alias="Stored Oxygen Level")
    stored_oxygen_level_unit: Optional[str] = Field(None, alias="Stored Oxygen Level Unit")
    incubation_temperature: Optional[str] = Field(None, alias="Incubation Temperature")
    incubation_temperature_unit: Optional[str] = Field(None, alias="Incubation Temperature Unit")

    # conditional fields (required if freezing_method != "fresh")
    freezing_date: Optional[Union[str, Literal["restricted access"]]] = Field(None, alias="Freezing Date")
    freezing_date_unit: Optional[Literal["YYYY-MM-DD", "YYYY-MM", "YYYY", "restricted access"]] = Field(None,
                                                                                                        alias="Unit")
    freezing_protocol: Optional[Union[str, Literal["restricted access"]]] = Field(None, alias="Freezing Protocol")


    @field_validator('sample_name')
    def validate_sample_name(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Sample Name is required and cannot be empty")
        return v.strip()


    @field_validator('organ_model_term_source_id')
    def validate_organ_model_term(cls, v, info):
        if v == "restricted access":
            return v

        term = v.replace('_', ':', 1)

        if term.startswith("UBERON:"):
            ontology_name = "UBERON"
            allowed_classes = ["UBERON:0001062"]
        elif term.startswith("BTO:"):
            ontology_name = "BTO"
            allowed_classes = ["BTO:0000042"]
        else:
            raise ValueError(f"Organ model term '{v}' should be from UBERON or BTO ontology")

        # ontology validation
        ov = OntologyValidator(cache_enabled=True)
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=allowed_classes,
            text=info.data.get('organ_model'),
            field_name='organ_model'
        )
        if res.errors:
            raise ValueError(f"Organ model term invalid: {res.errors}")

        return v

    @field_validator('organ_part_model_term_source_id')
    def validate_organ_part_term(cls, v, info):
        if not v or v == "restricted access":
            return v

        term = v.replace('_', ':', 1)

        if term.startswith("UBERON:"):
            ontology_name = "UBERON"
            allowed_classes = ["UBERON:0001062"]
        elif term.startswith("BTO:"):
            ontology_name = "BTO"
            allowed_classes = ["BTO:0000042"]
        else:
            raise ValueError(f"Organ part model term '{v}' should be from UBERON or BTO ontology")

        # ontology validation
        ov = OntologyValidator(cache_enabled=True)
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=allowed_classes,
            text=info.data.get('organ_part_model'),
            field_name='organ_part_model'
        )
        if res.errors:
            raise ValueError(f"Organ part model term invalid: {res.errors}")

        return v

    @field_validator('freezing_date')
    def validate_freezing_date_format(cls, v, info):
        if not v or v == "restricted access":
            return v

        values = info.data
        unit = values.get('Unit') or values.get('freezing_date_unit')

        if unit == "YYYY-MM-DD":
            pattern = r'^[12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$'
            date_format = '%Y-%m-%d'
        elif unit == "YYYY-MM":
            pattern = r'^[12]\d{3}-(0[1-9]|1[0-2])$'
            date_format = '%Y-%m'
        elif unit == "YYYY":
            pattern = r'^[12]\d{3}$'
            date_format = '%Y'
        else:
            return v

        if not re.match(pattern, v):
            raise ValueError(f"Invalid freezing date format: {v}. Must match {unit} pattern")

        try:
            datetime.strptime(v, date_format)
        except ValueError:
            raise ValueError(f"Invalid date value: {v}")

        return v

    @field_validator('organoid_passage_protocol', 'organoid_culture_and_passage_protocol', 'freezing_protocol')
    def validate_protocol_urls(cls, v):
        if not v or v == "restricted access":
            return v
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("Protocol must be a valid URL starting with http:// or https://")
        return v

    @field_validator('organoid_passage', mode='before')
    def validate_organoid_passage(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Organoid passage is required")

        try:
            passage_val = float(v)
            if passage_val < 0:
                raise ValueError("Organoid passage must be non-negative")
            return passage_val
        except ValueError as e:
            if "non-negative" in str(e):
                raise
            raise ValueError(f"Organoid passage must be a valid number, got '{v}'")

    @field_validator('number_of_frozen_cells', mode='before')
    def validate_number_of_frozen_cells(cls, v):
        if not v or (isinstance(v, str) and v.strip() == ""):
            return None

        try:
            cell_count = float(v)
            if cell_count < 0:
                raise ValueError("Number of frozen cells must be non-negative")
            return cell_count
        except ValueError as e:
            if "non-negative" in str(e):
                raise
            raise ValueError(f"Number of frozen cells must be a valid number, got '{v}'")

    @field_validator('derived_from')
    def validate_derived_from_value(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Derived from value is required and cannot be empty")
        return v.strip()

    # convert empty strings to None for optional fields
    @field_validator(
        'secondary_project', 'availability', 'same_as', 'organ_part_model', 'organ_part_model_term_source_id',
        'freezing_date', 'freezing_date_unit', 'freezing_protocol', 'number_of_frozen_cells_unit',
        'organoid_culture_and_passage_protocol', 'organoid_morphology',
        'growth_environment_unit', 'stored_oxygen_level', 'stored_oxygen_level_unit',
        'incubation_temperature', 'incubation_temperature_unit', mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        if v is not None and v.strip() == "":
            return None
        return v

    @model_validator(mode='after')
    def validate_conditional_requirements(self):
        freezing_method_value = self.freezing_method

        if freezing_method_value and freezing_method_value != "fresh":
            if not self.freezing_date:
                raise ValueError("Freezing date is required when freezing method is not 'fresh'")
            if not self.freezing_protocol:
                raise ValueError("Freezing protocol is required when freezing method is not 'fresh'")

        # organ part model consistency
        if self.organ_part_model and not self.organ_part_model_term_source_id:
            raise ValueError("Organ part model term source ID is required when organ part model text is provided")

        if (self.organ_part_model_term_source_id and
            self.organ_part_model_term_source_id != "restricted access" and
            (not self.organ_part_model or not self.organ_part_model.strip())):
            raise ValueError("Organ part model text is required when organ part model term source ID is provided")

        return self

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"