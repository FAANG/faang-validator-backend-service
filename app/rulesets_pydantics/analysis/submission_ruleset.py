from pydantic import BaseModel, Field, field_validator

class AnalysisSubmission(BaseModel):
    alias: str = Field(..., alias="Alias")

    @field_validator('alias')
    def validate_alias_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Alias is required and cannot be empty or whitespace")
        return v.strip()

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
