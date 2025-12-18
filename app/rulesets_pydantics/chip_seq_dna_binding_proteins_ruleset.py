from pydantic import BaseModel, Field, field_validator
from typing import Union, Literal, Optional
from app.validations.validation_utils import (
    normalize_ontology_term,
    strip_and_convert_empty_to_none
)
from app.validations.generic_validator_classes import get_ontology_validator


class ChipTarget(BaseModel):
    """Model for ChIP target with text and term."""
    text: str = Field(..., alias="text")
    term: Union[str, Literal["restricted access"]] = Field(..., alias="term")
    ontology_name: Optional[Literal["CHEBI", "OMIT", "NCIT"]] = Field(None, alias="ontology_name")

    @field_validator('term')
    def validate_chip_target_term(cls, v, info):
        if v == "restricted access":
            return v
        
        # Normalize the term (convert underscore to colon)
        term = normalize_ontology_term(v)
        
        # Get ontology name from field or infer from term
        ontology_name = info.data.get('ontology_name')
        if not ontology_name:
            if term.startswith("CHEBI:"):
                ontology_name = "CHEBI"
            elif term.startswith("OMIT:"):
                ontology_name = "OMIT"
            elif term.startswith("NCIT:"):
                ontology_name = "NCIT"
            else:
                # Default to CHEBI for ChIP targets
                ontology_name = "CHEBI"
        
        ov = get_ontology_validator()
        # Validate against CHEBI:15358 (protein) or other allowed classes
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=["CHEBI:15358"],  # protein
            text=info.data.get('text'),
            field_name='chip_target'
        )
        if res.errors:
            raise ValueError(f"ChIP target term invalid: {res.errors}")
        
        return v


class FAANGChipSeqDNABindingProteins(BaseModel):
    """
    Pydantic model for ChIP-seq DNA-binding proteins experiment metadata.
    Based on faang_experiments_chip-seq_dna-binding_proteins.metadata_rules.json
    """
    # required fields
    chip_target: ChipTarget = Field(
        ...,
        alias="chip target",
        description="The target of the ChIP-seq experiment e.g. H3K4Me3, H3K4Me1, H3K27Me3, H3K27Ac, CTCF."
    )
    chip_antibody_provider: str = Field(
        ...,
        alias="chip antibody provider",
        description="The name of the company, laboratory or person that provided the antibody e.g. Diagneode."
    )
    chip_antibody_catalog: str = Field(
        ...,
        alias="chip antibody catalog",
        description="The catalog from which the antibody was purchased e.g. pAb-003-050."
    )
    chip_antibody_lot: str = Field(
        ...,
        alias="chip antibody lot",
        description="The lot identifier of the antibody e.g. A5051-001P."
    )
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

    # recommended fields
    control_experiment: Optional[str] = Field(
        None,
        alias="control experiment",
        description="Experiment alias (in this submission) or ENA experiment accession (if submitted previously) of the ChIP-seq input DNA experiment which acts as the control/background for the analysis.",
        json_schema_extra={"recommended": True}
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

    @field_validator('chip_target', mode='before')
    def validate_chip_target_structure(cls, v):
        if isinstance(v, dict):
            # Handle case where chip_target comes as a dict with nested structure
            if 'text' in v and 'term' in v:
                return v
            # If it's a flat dict, try to extract values
            return v
        return v

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"


