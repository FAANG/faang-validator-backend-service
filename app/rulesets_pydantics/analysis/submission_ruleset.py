from pydantic import BaseModel, Field

class AnalysisSubmission(BaseModel):
    alias: str = Field(..., alias="Alias")

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"