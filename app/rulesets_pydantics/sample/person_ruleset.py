from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class FAANGPerson(BaseModel):
    # required fields
    person_last_name: str = Field(..., alias="Person Last Name")
    person_first_name: str = Field(..., alias="Person First Name")
    person_email: str = Field(..., alias="Person Email")
    person_role: Literal[
        "array manufacturer",
        "biomaterial provider",
        "biosequence provider",
        "consortium member",
        "consultant",
        "curator",
        "data analyst",
        "data coder",
        "experiment performer",
        "funder",
        "hardware manufacturer",
        "institution",
        "investigator",
        "material supplier role",
        "peer review quality control role",
        "software manufacturer",
        "submitter"
    ] = Field(..., alias="Person Role")

    # optional field
    person_initials: Optional[str] = Field(None, alias="Person Initials")

    @field_validator('person_last_name', 'person_first_name', 'person_email', 'person_role')
    def validate_mandatory_not_empty(cls, v, info):
        if not v or (isinstance(v, str) and v.strip() == ""):
            field_name = ' '.join(info.field_name.split('_')[1:]).title()
            raise ValueError(f"Person {field_name} is mandatory and cannot be empty")
        return v.strip() if isinstance(v, str) else v

    @field_validator('person_initials', mode='before')
    def convert_empty_to_none(cls, v):
        if v == "" or (isinstance(v, str) and v.strip() == ""):
            return None
        return v.strip() if isinstance(v, str) else v

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
