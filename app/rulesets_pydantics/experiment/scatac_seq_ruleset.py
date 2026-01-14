from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from app.validation.validation_utils import (
    validate_url,
    strip_and_convert_empty_to_none,
    normalize_ontology_term
)
from app.validation.generic_validator_classes import get_ontology_validator
from .core_ruleset import ExperimentCoreMetadata


class scATACSeqExperiment(ExperimentCoreMetadata):
    # required fields
    experiment_target: str = Field(..., alias="Experiment Target")
    experiment_target_term_source_id: Literal["SO:0001747", "restricted access"] = Field(
        ..., alias="Experiment Target Term Source ID")

    transposase_protocol: str = Field(..., alias="Transposase Protocol")
    
    transposed_dna_sequence_file_read_index: Literal["R1/R3", "restricted access"] = Field(
        ..., alias="Transposed DNA Sequence File Read Index")

    cell_barcode_read: Literal["R2", "restricted access"] = Field(..., alias="Cell Barcode Read")
    sample_index_read: Literal["I1", "restricted access"] = Field(..., alias="Sample Index Read")
    
    # optional fields
    nuclei_acid_molecule: Optional[str] = Field(None, alias="Nuclei Acid Molecule")
    nucleic_acid_source: Optional[str] = Field(None, alias="Nucleic Acid Source")
    sequencing_method: Optional[str] = Field(None, alias="Sequencing Method")
    kit_retail_name: Optional[str] = Field(None, alias="Kit Retail Name")
    kit_manufacturer: Optional[str] = Field(None, alias="Kit Manufacturer")
    sequencing_protocol: Optional[str] = Field(None, alias="Sequencing Protocol")
    library_construction_method: Optional[str] = Field(None, alias="Library Construction Method")
    
    # validators
    @field_validator('experiment_target_term_source_id')
    def validate_experiment_target_term(cls, v, info):
        if v == "restricted access":
            return v

        term = normalize_ontology_term(v)
        ov = get_ontology_validator()

        res = ov.validate_ontology_term(
            term=term,
            ontology_name="SO",
            allowed_classes=["SO:0001747"],
            text=info.data.get('experiment_target'),
            field_name='experiment_target'
        )
        if res.errors:
            raise ValueError(f"Experiment target term invalid: {res.errors}")

        return v

    @field_validator('transposase_protocol')
    def validate_transposase_protocol_url(cls, v):
        return validate_url(v, field_name="Transposase Protocol", allow_restricted=True)
    
    @field_validator(
        'nuclei_acid_molecule', 'nucleic_acid_source', 'sequencing_method',
        'kit_retail_name', 'kit_manufacturer', 'sequencing_protocol',
        'library_construction_method', mode='before'
    )
    def convert_empty_to_none(cls, v):
        return strip_and_convert_empty_to_none(v)
    
    class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"
