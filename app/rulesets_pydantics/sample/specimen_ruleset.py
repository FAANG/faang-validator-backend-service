from pydantic import BaseModel, Field, field_validator
from app.validation.generic_validator_classes import get_ontology_validator
from app.validation.validation_utils import (
    normalize_ontology_term,
    is_restricted_value,
    validate_sample_name,
    validate_date_format,
    validate_protocol_url,
    validate_non_negative_numeric,
    validate_percentage,
    validate_url,
    strip_and_convert_empty_to_none
)
from typing import List, Optional, Union, Literal

from .standard_ruleset import SampleCoreMetadata


class HealthStatus(BaseModel):
    text: str
    term: Union[str, Literal["not applicable", "not collected", "not provided", "restricted access"]]

    @field_validator('term')
    def validate_health_status(cls, v, info):
        if v in ["not applicable", "not collected", "not provided", "restricted access"]:
            return v

        term = normalize_ontology_term(v)

        if term.startswith("EFO:"):
            ontology_name = "EFO"
        elif term.startswith("PATO:"):
            ontology_name = "PATO"
        else:
            raise ValueError(f"Health status term '{v}' should be from PATO or EFO ontology")

        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=["PATO:0000461", "EFO:0000408"],
            text=info.data.get('text'),
            field_name='health_status'
        )
        if res.errors:
            raise ValueError(f"HealthStatus term invalid: {res.errors}")

        return v


class FAANGSpecimenFromOrganismSample(SampleCoreMetadata):
    # required fields
    sample_name: str = Field(..., alias="Sample Name")

    specimen_collection_date: Union[str, Literal["restricted access"]] = Field(..., alias="Specimen Collection Date")
    specimen_collection_date_unit: Literal["YYYY-MM-DD", "YYYY-MM", "YYYY", "restricted access"] = Field(...,
                                                                                                         alias="Unit")
    geographic_location: Literal[
        "Afghanistan", "Albania", "Algeria", "American Samoa", "Andorra", "Angola", "Anguilla",
        "Antarctica", "Antigua and Barbuda", "Arctic Ocean", "Argentina", "Armenia", "Aruba",
        "Ashmore and Cartier Islands", "Atlantic Ocean", "Australia", "Austria", "Azerbaijan", "Bahamas",
        "Bahrain", "Baltic Sea", "Baker Island", "Bangladesh", "Barbados", "Bassas da India", "Belarus",
        "Belgium", "Belize", "Benin", "Bermuda", "Bhutan", "Bolivia", "Borneo", "Bosnia and Herzegovina",
        "Botswana", "Bouvet Island", "Brazil", "British Virgin Islands", "Brunei", "Bulgaria", "Burkina Faso",
        "Burundi", "Cambodia", "Cameroon", "Canada", "Cape Verde", "Cayman Islands", "Central African Republic",
        "Chad", "Chile", "China", "Christmas Island", "Clipperton Island", "Cocos Islands", "Colombia", "Comoros",
        "Cook Islands", "Coral Sea Islands", "Costa Rica", "Cote d'Ivoire", "Croatia", "Cuba", "Curacao",
        "Cyprus", "Czech Republic", "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica",
        "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia",
        "Eswatini", "Ethiopia", "Europa Island", "Falkland Islands (Islas Malvinas)", "Faroe Islands", "Fiji",
        "Finland", "France", "French Guiana", "French Polynesia", "French Southern and Antarctic Lands", "Gabon",
        "Gambia", "Gaza Strip", "Georgia", "Germany", "Ghana", "Gibraltar", "Glorioso Islands", "Greece",
        "Greenland", "Grenada", "Guadeloupe", "Guam", "Guatemala", "Guernsey", "Guinea", "Guinea-Bissau",
        "Guyana", "Haiti", "Heard Island and McDonald Islands", "Honduras", "Hong Kong", "Howland Island",
        "Hungary", "Iceland", "India", "Indian Ocean", "Indonesia", "Iran", "Iraq", "Ireland", "Isle of Man",
        "Israel", "Italy", "Jamaica", "Jan Mayen", "Japan", "Jarvis Island", "Jersey", "Johnston Atoll", "Jordan",
        "Juan de Nova Island", "Kazakhstan", "Kenya", "Kerguelen Archipelago", "Kingman Reef", "Kiribati",
        "Kosovo", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya",
        "Liechtenstein", "Line Islands", "Lithuania", "Luxembourg", "Macau", "Madagascar", "Malawi", "Malaysia",
        "Maldives", "Mali", "Malta", "Marshall Islands", "Martinique", "Mauritania", "Mauritius", "Mayotte",
        "Mediterranean Sea", "Mexico", "Micronesia, Federated States of", "Midway Islands", "Moldova", "Monaco",
        "Mongolia", "Montenegro", "Montserrat", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru",
        "Navassa Island", "Nepal", "Netherlands", "New Caledonia", "New Zealand", "Nicaragua", "Niger", "Nigeria",
        "Niue", "Norfolk Island", "North Korea", "North Macedonia", "North Sea", "Northern Mariana Islands",
        "Norway", "Oman", "Pacific Ocean", "Pakistan", "Palau", "Palmyra Atoll", "Panama", "Papua New Guinea",
        "Paracel Islands", "Paraguay", "Peru", "Philippines", "Pitcairn Islands", "Poland", "Portugal",
        "Puerto Rico", "Qatar", "Republic of the Congo", "Reunion", "Romania", "Ross Sea", "Russia", "Rwanda",
        "Saint Barthelemy", "Saint Helena", "Saint Kitts and Nevis", "Saint Lucia", "Saint Martin",
        "Saint Pierre and Miquelon", "Saint Vincent and the Grenadines", "Samoa", "San Marino",
        "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore",
        "Sint Maarten", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa",
        "South Georgia and the South Sandwich Islands", "South Korea", "South Sudan", "Southern Ocean", "Spain",
        "Spratly Islands", "Sri Lanka", "State of Palestine", "Sudan", "Suriname", "Svalbard", "Sweden",
        "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Tasman Sea", "Thailand", "Timor-Leste",
        "Togo", "Tokelau", "Tonga", "Trinidad and Tobago", "Tromelin Island", "Tunisia", "Turkey", "Turkmenistan",
        "Turks and Caicos Islands", "Tuvalu", "USA", "Uganda", "Ukraine", "United Arab Emirates",
        "United Kingdom", "Uruguay", "Uzbekistan", "Vanuatu", "Venezuela", "Viet Nam", "Virgin Islands",
        "Wake Island", "Wallis and Futuna", "West Bank", "Western Sahara", "Yemen", "Zambia", "Zimbabwe",
        "Belgian Congo", "British Guiana", "Burma", "Czechoslovakia", "East Timor",
        "Former Yugoslav Republic of Macedonia", "Korea", "Macedonia", "Micronesia", "Netherlands Antilles",
        "Serbia and Montenegro", "Siam", "Swaziland", "The former Yugoslav Republic of Macedonia", "USSR",
        "Yugoslavia", "Zaire", "restricted access"
    ] = Field(..., alias="Geographic Location")

    animal_age_at_collection: Union[float, Literal["restricted access"]] = Field(..., alias="Animal Age At Collection")
    animal_age_at_collection_unit: Literal[
        "minutes", "hours", "month", "year", "days", "weeks", "months", "years",
        "minute", "hour", "day", "week", "restricted access"
    ] = Field(..., alias="Animal Age At Collection Unit")

    developmental_stage: str = Field(..., alias="Developmental Stage")
    developmental_stage_term_source_id: Union[str, Literal["restricted access"]] = Field(...,
                                                                                         alias="Developmental Stage Term Source ID")

    organism_part: str = Field(..., alias="Organism Part")
    organism_part_term_source_id: Union[str, Literal["restricted access"]] = Field(...,
                                                                                   alias="Organism Part Term Source ID")

    specimen_collection_protocol: Union[str, Literal["restricted access"]] = Field(...,
                                                                                   alias="Specimen Collection Protocol")
    derived_from: List[str] = Field(..., alias="Derived From")

    # recommended fields
    health_status: Optional[List[HealthStatus]] = Field(None, alias="Health Status",
                                                        json_schema_extra={"recommended": True})

    # optional fields
    fasted_status: Optional[Literal["fed", "fasted", "unknown"]] = Field(None, alias="Fasted Status")

    number_of_pieces: Optional[float] = Field(None, alias="Number of Pieces")
    number_of_pieces_unit: Optional[Literal["count"]] = Field("count", alias="Number of Pieces Unit")

    specimen_volume: Optional[float] = Field(None, alias="Specimen Volume")
    specimen_volume_unit: Optional[Literal["square centimeters", "liters", "milliliters"]] = Field(None,
                                                                                                   alias="Specimen Volume Unit")

    specimen_size: Optional[float] = Field(None, alias="Specimen Size")
    specimen_size_unit: Optional[Literal[
        "meters", "centimeters", "millimeters",
        "square meters", "square centimeters", "square millimeters"
    ]] = Field(None, alias="Specimen Size Unit")

    specimen_weight: Optional[float] = Field(None, alias="Specimen Weight")
    specimen_weight_unit: Optional[Literal["grams", "kilograms"]] = Field(None, alias="Specimen Weight Unit")

    specimen_picture_url: Optional[List[str]] = Field(None, alias="Specimen Picture URL")

    gestational_age_at_sample_collection: Optional[float] = Field(None, alias="Gestational Age At Sample Collection")
    gestational_age_at_sample_collection_unit: Optional[Literal["days", "weeks", "day", "week"]] = Field(None,
                                                                                                         alias="Gestational Age At Sample Collection Unit")

    average_incubation_temperature: Optional[float] = Field(None, alias="Average Incubation temperature")
    average_incubation_temperature_unit: Optional[Literal["degrees celsius"]] = Field("degrees celsius",
                                                                                      alias="Average Incubation temperature Unit")

    average_incubation_humidity: Optional[float] = Field(None, alias="Average Incubation Humidity")
    average_incubation_humidity_unit: Optional[Literal["%"]] = Field("%", alias="Average Incubation Humidity Unit")

    embryonic_stage: Optional[Literal[
        "Early cleavage", "During cleavage", "Late cleavage",
        "1", "2", "3", "4", "5", "6", "7", "7 to 8-", "8", "9",
        "9+ to 10-", "10", "11", "12", "13", "13+ to 14-", "14",
        "14+ to 15-", "15", "16", "17", "18", "19", "20", "21", "22", "23",
        "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34",
        "35", "36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46"
    ]] = Field(None, alias="Embryonic Stage")
    embryonic_stage_unit: Optional[Literal["stage Hamburger Hamilton"]] = Field("stage Hamburger Hamilton",
                                                                                alias="Embryonic Stage Unit")

    @field_validator('sample_name')
    def validate_sample_name_field(cls, v):
        return validate_sample_name(v)

    @field_validator('specimen_collection_date')
    def validate_specimen_collection_date_format(cls, v, info):
        values = info.data
        unit = values.get('Unit') or values.get('specimen_collection_date_unit')
        return validate_date_format(v, unit, "Specimen collection date")

    @field_validator('developmental_stage_term_source_id')
    def validate_developmental_stage_term(cls, v, info):
        if is_restricted_value(v):
            return v

        term = normalize_ontology_term(v)

        if term.startswith("EFO:"):
            ontology_name = "EFO"
            allowed_classes = ["EFO:0000399"]
        elif term.startswith("UBERON:"):
            ontology_name = "UBERON"
            allowed_classes = ["UBERON:0000105"]
        else:
            raise ValueError(f"Developmental stage term '{v}' should be from EFO or UBERON ontology")

        # ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=allowed_classes,
            text=info.data.get('developmental_stage'),
            field_name='developmental_stage'
        )
        if res.errors:
            raise ValueError(f"Developmental stage term invalid: {res.errors}")

        return v

    @field_validator('organism_part_term_source_id')
    def validate_organism_part_term(cls, v, info):
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
            raise ValueError(f"Organism part term '{v}' should be from UBERON or BTO ontology")

        # ontology validation
        ov = get_ontology_validator()
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=allowed_classes,
            text=info.data.get('organism_part'),
            field_name='organism_part'
        )
        if res.errors:
            raise ValueError(f"Organism part term invalid: {res.errors}")

        return v

    @field_validator('specimen_collection_protocol')
    def validate_protocol_url_field(cls, v):
        return validate_protocol_url(v, allow_restricted=True)

    @field_validator('animal_age_at_collection', mode='before')
    def validate_animal_age(cls, v):
        return validate_non_negative_numeric(v, "Animal age", allow_restricted=True)

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
            raise ValueError("Specimen samples must be derived from exactly one organism")
        return v


    # numeric fields
    @field_validator('number_of_pieces', 'specimen_volume', 'specimen_size', 'specimen_weight',
                     'gestational_age_at_sample_collection', 'average_incubation_temperature',
                     'average_incubation_humidity', mode='before')
    def validate_numeric_fields(cls, v):
        return validate_non_negative_numeric(v, "Numeric field", allow_restricted=True)

    @field_validator('average_incubation_humidity')
    def validate_humidity_range(cls, v):
        return validate_percentage(v, "Humidity")

    @field_validator('specimen_picture_url')
    def validate_picture_urls(cls, v):
        if not v:
            return v

        validated_urls = []
        for url in v:
            if url and url.strip():
                validated_url = validate_url(url, field_name="Picture URL", allow_restricted=False)
                validated_urls.append(validated_url)

        return validated_urls if validated_urls else None

    # convert empty strings to None for optional fields
    @field_validator(
        'fasted_status', 'number_of_pieces', 'specimen_volume', 'specimen_size', 'specimen_weight',
        'gestational_age_at_sample_collection', 'average_incubation_temperature', 'average_incubation_humidity',
        'embryonic_stage', 'specimen_picture_url',
        'number_of_pieces_unit', 'specimen_volume_unit', 'specimen_size_unit', 'specimen_weight_unit',
        'gestational_age_at_sample_collection_unit', 'average_incubation_temperature_unit',
        'average_incubation_humidity_unit', 'embryonic_stage_unit', mode='before'
    )
    def convert_empty_strings_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"