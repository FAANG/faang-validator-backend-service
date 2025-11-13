from pydantic import Field, field_validator, model_validator
from app.validations.generic_validator_classes import get_ontology_validator
from app.validations.validation_utils import (
    normalize_ontology_term,
    is_restricted_value,
    validate_sample_name,
    validate_date_format,
    validate_protocol_url,
    validate_non_negative_numeric,
    strip_and_convert_empty_to_none
)
from typing import Optional, Union, Literal, List
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
    derived_from: List[str] = Field(..., alias="Derived From")

    # Optional fields
    organ_part_model: Optional[str] = Field(None, alias="Organ Part Model")
    organ_part_model_term_source_id: Optional[Union[str, Literal["restricted access"]]] = Field(None,
                                                                                                alias="Organ Part Model Term Source ID")
    number_of_frozen_cells: Optional[float] = Field(None, alias="Number Of Frozen Cells")
    number_of_frozen_cells_unit: Optional[Literal["organoids"]] = Field("organoids",
                                                                        alias="Number Of Frozen Cells Unit")
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
    def validate_sample_name_field(cls, v):
        return validate_sample_name(v)

    @field_validator('organ_model_term_source_id')
    def validate_organ_model_term(cls, v, info):
        if is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if term.startswith("UBERON:"):
            ontology_name = "UBERON"
            allowed_classes = ["UBERON:0001062"]
        elif term.startswith("BTO:"):
            ontology_name = "BTO"
            allowed_classes = ["BTO:0000042"]
        else:
            raise ValueError(f"Organ model term '{v}' should be from UBERON or BTO ontology")

        # ontology validation
        ov = get_ontology_validator()
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
        if is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if term.startswith("UBERON:"):
            ontology_name = "UBERON"
            allowed_classes = ["UBERON:0001062"]
        elif term.startswith("BTO:"):
            ontology_name = "BTO"
            allowed_classes = ["BTO:0000042"]
        else:
            raise ValueError(f"Organ part model term '{v}' should be from UBERON or BTO ontology")

        # ontology validation
        ov = get_ontology_validator()
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
        if is_restricted_value(v):
            return v

        values = info.data
        unit = values.get('Unit') or values.get('freezing_date_unit')

        # Validate format
        validated_date = validate_date_format(v, unit, "Freezing date")

        # Additional validation: check if it's a valid date
        if validated_date and validated_date not in ["not applicable", "not collected", "not provided",
                                                     "restricted access", ""]:
            if unit == "YYYY-MM-DD":
                date_format = '%Y-%m-%d'
            elif unit == "YYYY-MM":
                date_format = '%Y-%m'
            elif unit == "YYYY":
                date_format = '%Y'
            else:
                return validated_date

            try:
                datetime.strptime(validated_date, date_format)
            except ValueError:
                raise ValueError(f"Invalid date value: {validated_date}")

        return validated_date

    @field_validator('organoid_passage_protocol', 'organoid_culture_and_passage_protocol', 'freezing_protocol')
    def validate_protocol_urls(cls, v):
        return validate_protocol_url(v, allow_restricted=True)

    @field_validator('organoid_passage', mode='before')
    def validate_organoid_passage(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Organoid passage is required")

        passage_val = validate_non_negative_numeric(v, "Organoid passage", allow_restricted=False)
        if passage_val is None:
            raise ValueError("Organoid passage is required")

        return passage_val

    @field_validator('number_of_frozen_cells', mode='before')
    def validate_number_of_frozen_cells(cls, v):
        return validate_non_negative_numeric(v, "Number of frozen cells", allow_restricted=False)


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
            raise ValueError("Organoid samples must be derived from exactly one specimen")
        return v

    # convert empty strings to None for optional fields
    @field_validator(
        'secondary_project', 'availability', 'same_as', 'organ_part_model', 'organ_part_model_term_source_id',
        'freezing_date', 'freezing_date_unit', 'freezing_protocol', 'number_of_frozen_cells_unit',
        'organoid_culture_and_passage_protocol', 'organoid_morphology',
        'growth_environment_unit', 'stored_oxygen_level', 'stored_oxygen_level_unit',
        'incubation_temperature', 'incubation_temperature_unit', mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

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