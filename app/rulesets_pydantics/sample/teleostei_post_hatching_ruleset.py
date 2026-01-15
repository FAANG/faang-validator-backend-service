from pydantic import Field, field_validator
from app.validation.validation_utils import (
    validate_photoperiod,
    validate_time_format,
    validate_non_negative_numeric,
    validate_percentage,
    strip_and_convert_empty_to_none,
    normalize_ontology_term,
    is_restricted_value
)
from typing import Optional, Union, Literal
from app.rulesets_pydantics.sample.specimen_ruleset import FAANGSpecimenFromOrganismSample
from app.validation.generic_validator_classes import get_ontology_validator


class FAANGTeleosteiPostHatchingSample(FAANGSpecimenFromOrganismSample):
    # required fields
    sample_name: str = Field(..., alias="Sample Name")

    origin: Literal[
        "Domesticated diploid",
        "Domesticated Double-haploid",
        "Domesticated Isogenic",
        "Wild",
        "restricted access"
    ] = Field(..., alias="Origin")

    reproductive_strategy: Literal[
        "gonochoric",
        "simultaneous hermaphrodite",
        "successive hermaphrodite",
        "restricted access"
    ] = Field(..., alias="Reproductive Strategy")

    gonad_type: Literal[
        "testis",
        "ovary",
        "intersexual/transitional stage",
        "ovotestis",
        "restricted access"
    ] = Field(..., alias="Gonad Type")

    hatching: Literal["pre", "post", "restricted access"] = Field(..., alias="Hatching")

    maturity_state: str = Field(..., alias="Maturity State")
    maturity_state_term_source_id: Union[str, Literal["restricted access"]] = Field(
        ..., alias="Maturity State Term Source ID"
    )

    time_post_fertilisation: Union[float, Literal["restricted access"]] = Field(
        ..., alias="Time Post Fertilisation"
    )
    time_post_fertilisation_unit: Literal[
        "hours", "days", "months", "years", "restricted access"
    ] = Field(..., alias="Time Post Fertilisation Unit")

    post_hatching_animal_density: Union[float, Literal["restricted access"]] = Field(
        ..., alias="Post-hatching Animal Density"
    )
    post_hatching_animal_density_unit: Literal[
        "Kg/L", "Kg/m2", "Kg/m3", "restricted access"
    ] = Field(..., alias="Post-hatching Animal Density Unit")

    food_restriction: Union[float, Literal["restricted access"]] = Field(
        ..., alias="Food Restriction"
    )
    food_restriction_unit: Literal["hours", "restricted access"] = Field(
        ..., alias="Food Restriction Unit"
    )

    post_hatching_water_temperature_average: Union[float, Literal["restricted access"]] = Field(
        ..., alias="Post-hatching Water Temperature Average"
    )
    post_hatching_water_temperature_average_unit: Literal[
        "Degrees celsius", "restricted access"
    ] = Field(..., alias="Post-hatching Water Temperature Average Unit")

    average_water_salinity: Union[float, Literal["restricted access"]] = Field(
        ..., alias="Average Water Salinity"
    )
    average_water_salinity_unit: Literal[
        "parts per thousand", "restricted access"
    ] = Field(..., alias="Average Water Salinity Unit")

    photoperiod: Union[str, Literal["natural light", "restricted access"]] = Field(
        ..., alias="Photoperiod"
    )

    sampling_weight: Union[float, Literal["restricted access"]] = Field(
        ..., alias="Sampling Weight"
    )
    sampling_weight_unit: Literal["grams", "kilograms", "restricted access"] = Field(
        ..., alias="Sampling Weight Unit"
    )

    method_of_euthanasia: Literal[
        "Non-lethal anaesthetic and exsanguination",
        "Non-lethal anaesthetic and severing spinal cord",
        "Lethal anaesthetic",
        "Lethal anaesthetic and exsanguination",
        "Lethal anaesthetic and severing spinal cord",
        "Concussive blow and exsanguination",
        "Concussive blow and severing spinal cord",
        "restricted access"
    ] = Field(..., alias="Method Of Euthanasia")

    # recommended fields
    generations_from_wild: Optional[Union[float, Literal[
        "not applicable", "not collected", "not provided", "restricted access"
    ]]] = Field(None, alias="Generations From Wild", json_schema_extra={"recommended": True})

    generations_from_wild_unit: Optional[Literal[
        "generations from wild",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access"
    ]] = Field(None, alias="Generations From Wild Unit", json_schema_extra={"recommended": True})

    diet: Optional[str] = Field(None, alias="Diet", json_schema_extra={"recommended": True})

    standard_length: Optional[Union[float, Literal["restricted access"]]] = Field(
        None, alias="Standard Length", json_schema_extra={"recommended": True}
    )
    standard_length_unit: Optional[Literal["millimeters", "centimeters", "restricted access"]] = Field(
        None, alias="Standard Length Unit", json_schema_extra={"recommended": True}
    )

    total_length: Optional[Union[float, Literal["restricted access"]]] = Field(
        None, alias="Total Length", json_schema_extra={"recommended": True}
    )
    total_length_unit: Optional[Literal["millimeters", "centimeters", "restricted access"]] = Field(
        None, alias="Total Length Unit", json_schema_extra={"recommended": True}
    )

    fork_length: Optional[Union[float, Literal["restricted access"]]] = Field(
        None, alias="Fork Length", json_schema_extra={"recommended": True}
    )
    fork_length_unit: Optional[Literal["millimeters", "centimeters", "restricted access"]] = Field(
        None, alias="Fork Length Unit", json_schema_extra={"recommended": True}
    )

    # optional fields
    experimental_strain_id: Optional[str] = Field(None, alias="Experimental Strain Id")
    genetic_background: Optional[str] = Field(None, alias="Genetic Background")

    water_rearing_system: Optional[Literal[
        "Closed water system (recirculatory)",
        "Open water system",
        "restricted access"
    ]] = Field(None, alias="Water Rearing System")

    average_water_oxygen: Optional[Union[float, Literal["restricted access"]]] = Field(
        None, alias="Average Water Oxygen"
    )
    average_water_oxygen_unit: Optional[Literal["%", "mg/L", "restricted access"]] = Field(
        None, alias="Average Water Oxygen Unit"
    )

    sampling_day_start_time: Optional[str] = Field(None, alias="Sampling Day Start Time")
    sampling_day_end_time: Optional[str] = Field(None, alias="Sampling Day End Time")

    anaesthetic_or_sedative_name: Optional[Literal[
        "Tricaine methanesulfonate (MS-222)",
        "Tert-butyl hydroperoxide (TBH)",
        "Benzocaine",
        "Clove oil",
        "2-phenoxyethanol",
        "restricted access"
    ]] = Field(None, alias="Anaesthetic Or Sedative Name")

    # validators
    @field_validator('maturity_state_term_source_id')
    def validate_maturity_state_term(cls, v, info):
        if is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if not term.startswith("PATO:"):
            raise ValueError(f"Maturity state term '{v}' should be from PATO ontology")

        # PATO:0001501 (Immature) | PATO:0001701 (Mature)
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name="PATO",
            allowed_classes=["PATO:0001501", "PATO:0001701"],
            text=info.data.get('maturity_state'),
            field_name='maturity_state'
        )
        if res.errors:
            raise ValueError(f"Maturity state term invalid: {res.errors}")

        return v

    @field_validator('photoperiod')
    def validate_photoperiod_field(cls, v):
        return validate_photoperiod(v)

    @field_validator('sampling_day_start_time', 'sampling_day_end_time')
    def validate_time_format_field(cls, v):
        return validate_time_format(v, "Sampling time")

    @field_validator(
        'time_post_fertilisation',
        'post_hatching_animal_density',
        'food_restriction',
        'post_hatching_water_temperature_average',
        'average_water_salinity',
        'sampling_weight',
        'generations_from_wild',
        'standard_length',
        'total_length',
        'fork_length',
        'average_water_oxygen',
        mode='before'
    )
    def validate_numeric_fields(cls, v):
        return validate_non_negative_numeric(v, "Numeric field", allow_restricted=True)

    @field_validator('average_water_oxygen')
    def validate_oxygen_range(cls, v):
        if is_restricted_value(v) or v is None:
            return v

        # check if percentage (0-100) or mg/L (any positive)
        # we'll assume percentage if <= 100
        if v > 100:
            return v  # Assume it's mg/L

        return validate_percentage(v, "Water oxygen")

    # convert empty strings to None for all optional fields
    @field_validator(
        'generations_from_wild', 'generations_from_wild_unit',
        'experimental_strain_id', 'genetic_background',
        'water_rearing_system', 'diet',
        'standard_length', 'standard_length_unit',
        'total_length', 'total_length_unit',
        'fork_length', 'fork_length_unit',
        'average_water_oxygen', 'average_water_oxygen_unit',
        'sampling_day_start_time', 'sampling_day_end_time',
        'anaesthetic_or_sedative_name',
        mode='before'
    )
    def strip_and_convert_empty(cls, v):
        return strip_and_convert_empty_to_none(v)

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"