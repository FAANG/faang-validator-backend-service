from pydantic import BaseModel, Field, field_validator


class FAANGSubmission(BaseModel):
    submission_title: str = Field(..., alias="Submission Title")
    submission_description: str = Field(..., alias="Submission Description")

    @field_validator('submission_title', 'submission_description')
    def validate_not_empty(cls, v, info):
        if not v or (isinstance(v, str) and v.strip() == ""):
            field_name = info.field_name.replace('_', ' ').title()
            raise ValueError(f"{field_name} is mandatory and cannot be empty")
        return v.strip() if isinstance(v, str) else v

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"