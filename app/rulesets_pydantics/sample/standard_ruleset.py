from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal


class SampleCoreMetadata(BaseModel):
    # required fields
    sample_description: Optional[str] = Field(None, alias="Sample Description")
    material: Literal[
        "organism",
        "specimen from organism",
        "cell specimen",
        "single cell specimen",
        "pool of specimens",
        "cell culture",
        "cell line",
        "organoid",
        "restricted access"
    ] = Field(..., alias="Material")
    term_source_id: Literal[
        "OBI_0100026",  # organism
        "OBI_0001479",  # specimen from organism
        "OBI_0001468",  # cell specimen
        "OBI_0002127",  # single cell specimen
        "OBI_0302716",  # pool of specimens
        "OBI_0001876",  # cell culture
        "CLO_0000031",  # cell line
        "NCIT_C172259",  # organoid
        "restricted access"
    ] = Field(..., alias="Term Source ID")

    project: Literal["FAANG"] = Field(..., alias="Project")

    # optional fields
    secondary_project: Optional[List[Literal[
        "AQUA-FAANG",
        "BovReg",
        "GENE-SWitCH",
        "Bovine-FAANG",
        "EFFICACE",
        "GEroNIMO",
        "RUMIGEN",
        "Equine-FAANG",
        "Holoruminant",
        "USPIGFAANG"
    ]]] = Field(None, alias="Secondary Project")

    availability: Optional[str] = Field(None, alias="Availability")
    same_as: Optional[str] = Field(None, alias="Same as")

    @field_validator('term_source_id')
    def validate_material_term(cls, v, info):
        values = info.data
        material = values.get('Material') or values.get('material')

        material_term_mapping = {
            "organism": "OBI_0100026",
            "specimen from organism": "OBI_0001479",
            "cell specimen": "OBI_0001468",
            "single cell specimen": "OBI_0002127",
            "pool of specimens": "OBI_0302716",
            "cell culture": "OBI_0001876",
            "cell line": "CLO_0000031",
            "organoid": "NCIT_C172259",
            "restricted access": "restricted access",
        }

        expected_term = material_term_mapping.get(material)
        if expected_term and v != expected_term:
            raise ValueError(f"Term '{v}' does not match material '{material}'. Expected: '{expected_term}'")

        return v

    @field_validator('availability')
    def validate_availability_format(cls, v):
        if not v or v.strip() == "":
            return v

        if not (v.startswith('http://') or v.startswith('https://') or v.startswith('mailto:')):
            raise ValueError("Availability must be a web URL or email address with 'mailto:' prefix")
        return v

    @field_validator('secondary_project', mode='before')
    def validate_secondary_project(cls, v):
        if not v:
            return None

        if isinstance(v, str):
            if v.strip() == "":
                return None
            v = [v]

        if isinstance(v, list):
            filtered = [item for item in v if item and isinstance(item, str) and item.strip()]
            return filtered if filtered else None

        return v

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"