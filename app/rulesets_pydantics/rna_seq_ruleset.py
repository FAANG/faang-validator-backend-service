from pydantic import BaseModel, Field, field_validator
from typing import Union, Literal, Optional
from app.validations.validation_utils import (
    normalize_ontology_term,
    strip_and_convert_empty_to_none
)
from app.validations.generic_validator_classes import get_ontology_validator
from app.rulesets_pydantics.experiment_core_ruleset import ExperimentCoreMetadata


class ExperimentTarget(BaseModel):
    """Model for experiment target with text and term."""
    text: Union[str, Literal["restricted access"]] = Field(..., alias="text")
    term: Union[str, Literal["restricted access"]] = Field(..., alias="term")
    ontology_name: Optional[Literal["EFO"]] = Field(None, alias="ontology_name")
    
    class Config:
        populate_by_name = True

    @field_validator('term')
    @classmethod
    def validate_experiment_target_term(cls, v, info):
        if v == "restricted access":
            return v
        
        # Normalize the term (convert underscore to colon)
        term = normalize_ontology_term(v)
        
        # Get ontology name from field or infer from term
        ontology_name = info.data.get('ontology_name', 'EFO')
        
        ov = get_ontology_validator()
        # Validate against CHEBI:33697 (RNA) or other allowed classes
        res = ov.validate_ontology_term(
            term=term,
            ontology_name=ontology_name,
            allowed_classes=["CHEBI:33697"],  # RNA
            text=info.data.get('text'),
            field_name='experiment_target'
        )
        if res.errors:
            raise ValueError(f"Experiment target term invalid: {res.errors}")
        
        return v


class URIValueItem(BaseModel):
    """Model for URI protocol fields."""
    value: Union[str, Literal["restricted access"]] = Field(..., alias="value")

    @field_validator('value', mode='before')
    @classmethod
    def validate_uri_before(cls, v):
        # If it's already a dict with 'value', extract the value
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v

    @field_validator('value')
    @classmethod
    def validate_uri(cls, v):
        if v == "restricted access":
            return v
        # Allow any string - URI validation can be done separately if needed
        if isinstance(v, str):
            return v
        raise ValueError("Value must be a string or 'restricted access'")

    class Config:
        populate_by_name = True


class ReadStrandValueItem(BaseModel):
    """Model for read strand enum field."""
    value: Literal[
        "not applicable",
        "sense",
        "antisense",
        "mate 1 sense",
        "mate 2 sense",
        "non-stranded",
        "restricted access"
    ] = Field(..., alias="value")

    @field_validator('value', mode='before')
    @classmethod
    def validate_read_strand_before(cls, v):
        # If it's already a dict with 'value', extract the value
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v

    class Config:
        populate_by_name = True


class NumberOrEnumValueItem(BaseModel):
    """Model for number or enum fields (for recommended fields)."""
    value: Union[
        float,
        Literal[
            "not applicable",
            "not collected",
            "not provided",
            "restricted access"
        ]
    ] = Field(..., alias="value")

    @field_validator('value', mode='before')
    @classmethod
    def validate_value(cls, v):
        if isinstance(v, dict) and 'value' in v:
            return v['value']
        return v

    @field_validator('value')
    @classmethod
    def validate_value_type(cls, v):
        if v in ["not applicable", "not collected", "not provided", "restricted access"]:
            return v
        if isinstance(v, (int, float)):
            return float(v)
        raise ValueError("Value must be a number or one of the allowed enum values")

    class Config:
        populate_by_name = True


class FAANGRNASeq(ExperimentCoreMetadata):
    """
    Pydantic model for RNA-seq experiment metadata.
    Based on faang_experiments_rna-seq.metadata_rules.json
    """
    # required fields
    experiment_target: ExperimentTarget = Field(
        ...,
        alias="Experiment Target",
        description="What the experiment was trying to find, list the text rather than ontology link, for example 'polyA RNA'."
    )
    rna_preparation_3_adapter_ligation_protocol: URIValueItem = Field(
        ...,
        alias="Rna Preparation 3' adapter ligation protocol",
        description="Link to the protocol for 3' adapter ligation used in preparation."
    )
    rna_preparation_5_adapter_ligation_protocol: URIValueItem = Field(
        ...,
        alias="Rna Preparation 5' adapter ligation protocol",
        description="Link to the protocol for 5' adapter ligation used in preparation."
    )
    library_generation_pcr_product_isolation_protocol: URIValueItem = Field(
        ...,
        alias="Library Generation PCR Product Isolation Protocol",
        description="Link to the protocol for isolating pcr products used for library generation."
    )
    preparation_reverse_transcription_protocol: URIValueItem = Field(
        ...,
        alias="Preparation Reverse Transcription Protocol",
        description="Link to the protocol for reverse transcription used in preparation."
    )
    library_generation_protocol: URIValueItem = Field(
        ...,
        alias="Library Generation Protocol",
        description="Link to the protocol used to generate the library."
    )
    read_strand: ReadStrandValueItem = Field(
        ...,
        alias="Read Strand",
        description="For strand specific protocol, specify which mate pair maps to the transcribed strand or Report 'non-stranded' if the protocol is not strand specific."
    )

    # recommended fields
    rna_purity_260_280_ratio: Optional[NumberOrEnumValueItem] = Field(
        None,
        alias="RNA Purity 260-280 ratio",
        description="Sample purity assessed with fluorescence ratio at 260 and 280nm, informative for protein contamination.",
        json_schema_extra={"recommended": True}
    )
    rna_purity_260_230_ratio: Optional[NumberOrEnumValueItem] = Field(
        None,
        alias="RNA Purity 260-230 ratio",
        description="Sample purity assessed with fluorescence ratio at 260 and 230nm, informative for contamination by phenolate ion, thiocyanates, and other organic compounds.",
        json_schema_extra={"recommended": True}
    )
    rna_integrity_number: Optional[NumberOrEnumValueItem] = Field(
        None,
        alias="RNA Integrity Number",
        description="It is important to obtain this value, but if you are unable to supply this number (e.g. due to machine failure) then by submitting you are asserting the quality by visual inspection of traces and agreeing that the samples were suitable for sequencing.",
        json_schema_extra={"recommended": True}
    )

    @field_validator('experiment_target', mode='before')
    @classmethod
    def validate_experiment_target_structure(cls, v):
        if isinstance(v, dict):
            # Handle case where experiment_target comes as a dict with nested structure
            if 'text' in v and 'term' in v:
                return v
            # If it's a flat dict, try to extract values
            return v
        # If it's a string, convert to dict with text and empty term
        if isinstance(v, str) and v:
            return {"text": v, "term": ""}
        return v

    @field_validator(
        'rna_preparation_3_adapter_ligation_protocol',
        'rna_preparation_5_adapter_ligation_protocol',
        'library_generation_pcr_product_isolation_protocol',
        'preparation_reverse_transcription_protocol',
        'library_generation_protocol',
        mode='before'
    )
    @classmethod
    def validate_protocol_structure(cls, v):
        if isinstance(v, dict):
            if 'value' in v:
                return v
            # If it's already a URI string, wrap it
            if isinstance(v.get('value'), str) or 'value' not in v:
                return v
        # If it's a string, convert to dict with value
        if isinstance(v, str) and v:
            return {"value": v}
        return v

    @field_validator('read_strand', mode='before')
    @classmethod
    def validate_read_strand_structure(cls, v):
        if isinstance(v, dict):
            if 'value' in v:
                return v
        # If it's a string, convert to dict with value
        if isinstance(v, str) and v:
            return {"value": v}
        return v

    @field_validator(
        'rna_purity_260_280_ratio',
        'rna_purity_260_230_ratio',
        'rna_integrity_number',
        mode='before'
    )
    @classmethod
    def validate_ratio_structure(cls, v):
        if v is None:
            return v
        if isinstance(v, dict):
            if 'value' in v:
                return v
        # If it's a number or string, convert to dict with value
        if isinstance(v, (int, float, str)) and v:
            return {"value": v}
        return v

    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"

