from pydantic import BaseModel, Field, field_validator
from typing import Union, Literal
from app.validations.validation_utils import strip_and_convert_empty_to_none


class FAANGChipSeqInputDNA(BaseModel):
    """
    Pydantic model for ChIP-seq input DNA experiment metadata.
    Based on faang_experiments_chip-seq_input_dna.metadata_rules.json
    """
    # required fields
    library_generation_max_fragment_size_range: Union[float, Literal["restricted access"]] = Field(
        ...,
        alias="library generation max fragment size range",
        description="The maximum fragment size range of the preparation."
    )
    library_generation_min_fragment_size_range: Union[float, Literal["restricted access"]] = Field(
        ...,
        alias="library generation min fragment size range",
        description="The minimum fragment size range of the preparation."
    )

    @field_validator('library_generation_max_fragment_size_range', 'library_generation_min_fragment_size_range', mode='before')
    def validate_fragment_size(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v

    @field_validator('library_generation_max_fragment_size_range', 'library_generation_min_fragment_size_range')
    def validate_fragment_size_type(cls, v):
        if v == "restricted access":
            return v
        if isinstance(v, (int, float)):
            if v < 0:
                raise ValueError("Fragment size must be non-negative")
            return float(v)
        raise ValueError("Fragment size must be a number or 'restricted access'")

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"


