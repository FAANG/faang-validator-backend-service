from pydantic import BaseModel, Field, field_validator

class ExperimentStudy(BaseModel):
    study_alias: str = Field(..., alias="Study Alias")
    study_title: str = Field(..., alias="Study Title")
    study_type: str = Field(..., alias="Study Type")
    study_abstract: str = Field(..., alias="Study Abstract")

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
