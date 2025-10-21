from pydantic import BaseModel, Field, field_validator
from app.validations.validation_utils import (
    validate_sample_name,
    validate_date_format,
    validate_protocol_url,
    validate_non_negative_numeric,
    validate_url,
    strip_and_convert_empty_to_none
)
from typing import List, Optional, Union, Literal
from .standard_ruleset import SampleCoreMetadata


class FAANGPoolOfSpecimensSample(SampleCoreMetadata):
    # required fields
    sample_name: str = Field(..., alias="Sample Name")

    pool_creation_date: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Pool Creation Date"
    )
    pool_creation_date_unit: Literal[
        "YYYY-MM-DD", "YYYY-MM", "YYYY", "restricted access"
    ] = Field(..., alias="Unit")

    pool_creation_protocol: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Pool Creation Protocol"
    )

    derived_from: List[str] = Field(..., alias="Derived From")

    # optional fields
    specimen_volume: Optional[float] = Field(None, alias="Specimen Volume")
    specimen_volume_unit: Optional[Literal[
        "square centimeters", "liters", "milliliters"
    ]] = Field(None, alias="Specimen Volume Unit")

    specimen_size: Optional[float] = Field(None, alias="Specimen Size")
    specimen_size_unit: Optional[Literal[
        "meters", "centimeters", "millimeters",
        "square meters", "square centimeters", "square millimeters"
    ]] = Field(None, alias="Specimen Size Unit")

    specimen_weight: Optional[float] = Field(None, alias="Specimen Weight")
    specimen_weight_unit: Optional[Literal["grams", "kilograms"]] = Field(
        None, alias="Specimen Weight Unit"
    )

    specimen_picture_url: Optional[List[str]] = Field(None, alias="Specimen Picture URL")

    # validators
    @field_validator('sample_name')
    def validate_sample_name_field(cls, v):
        return validate_sample_name(v)

    @field_validator('pool_creation_date')
    def validate_pool_creation_date_format(cls, v, info):
        if v == "restricted access":
            return v

        # Strip timestamp if present (handle "2018-07-12 00:00:00" format)
        if ' ' in str(v):
            v = str(v).split(' ')[0]

        values = info.data
        unit = values.get('Unit') or values.get('pool_creation_date_unit')
        return validate_date_format(v, unit, "Pool creation date")

    @field_validator('pool_creation_protocol')
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
                raise ValueError("Derived from must contain at least one valid value")
            return non_empty

        raise ValueError("Derived from must be a string or list of strings")

    @field_validator('derived_from')
    def validate_multiple_parents(cls, v):
        if len(v) < 1:
            raise ValueError("Pool of specimens must be derived from at least one specimen")
        return v

    @field_validator('specimen_volume', 'specimen_size', 'specimen_weight', mode='before')
    def validate_numeric_fields(cls, v):
        return validate_non_negative_numeric(v, "Numeric field", allow_restricted=False)

    @field_validator('specimen_picture_url')
    def validate_picture_urls(cls, v):
        if not v:
            return v

        validated_urls = []
        for url in v:
            if url and str(url).strip():
                validated_url = validate_url(url, field_name="Picture URL", allow_restricted=False)
                validated_urls.append(validated_url)

        return validated_urls if validated_urls else None

    # convert empty strings to None for optional fields
    @field_validator(
        'secondary_project', 'availability', 'same_as',
        'specimen_volume', 'specimen_volume_unit',
        'specimen_size', 'specimen_size_unit',
        'specimen_weight', 'specimen_weight_unit',
        'specimen_picture_url',
        mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"