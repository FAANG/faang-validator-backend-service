from pydantic import BaseModel, Field, field_validator


class FAANGOrganization(BaseModel):
    # required fields
    organization_name: str = Field(..., alias="Organization Name")
    organization_address: str = Field(..., alias="Organization Address")
    organization_uri: str = Field(..., alias="Organization URI")
    organization_role: str = Field(..., alias="Organization Role")

    @field_validator('organization_name', 'organization_address', 'organization_uri', 'organization_role')
    def validate_not_empty(cls, v, info):
        if not v or (isinstance(v, str) and v.strip() == ""):
            field_name = ' '.join(info.field_name.split('_')[1:]).title()
            raise ValueError(f"Organization {field_name} is mandatory and cannot be empty")
        return v.strip() if isinstance(v, str) else v

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"