from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, Literal, Union


class ExperimentCoreMetadata(BaseModel):
    """
    Base metadata class for FAANG experiments.
    Contains core fields from experiments_core.metadata_rules.json
    """
    # Core experiment fields
    sample_descriptor: Optional[str] = Field(None, alias="Sample Descriptor")
    experiment_alias: Optional[str] = Field(None, alias="Experiment Alias")
    project: Optional[Literal["FAANG"]] = Field(None, alias="Project")
    secondary_project: Optional[Literal[
        "AQUA-FAANG",
        "BovReg",
        "GENE-SWitCH",
        "Bovine-FAANG",
        "EFFICACE",
        "GEroNIMO",
        "RUMIGEN",
        "Equine-FAANG",
        "Holoruminant",
        "USPIGFAANG"
    ]] = Field(None, alias="Secondary Project")

    @field_validator('secondary_project', mode='before')
    @classmethod
    def validate_secondary_project(cls, v):
        if not v or v.strip() == "":
            return None
        return v

    assay_type: Optional[str] = Field(None, alias="Assay Type")
    sample_storage: Optional[str] = Field(None, alias="Sample Storage")
    sample_storage_processing: Optional[str] = Field(None, alias="Sample Storage Processing")
    sampling_to_preparation_interval: Optional[Union[float, str]] = Field(None, alias="Sampling to Preparation Interval")
    unit: Optional[str] = Field(None, alias="Unit")
    experimental_protocol: Optional[Union[HttpUrl, str]] = Field(None, alias="Experimental Protocol")
    extraction_protocol: Optional[Union[HttpUrl, str]] = Field(None, alias="Extraction Protocol")
    library_preparation_location: Optional[str] = Field(None, alias="Library Preparation Location")
    library_preparation_location_longitude: Optional[Union[float, str]] = Field(None, alias="Library Preparation Location Longitude")
    library_preparation_location_longitude_unit: Optional[str] = Field(None, alias="Library Preparation Location Longitude Unit")
    library_preparation_location_latitude: Optional[Union[float, str]] = Field(None, alias="Library Preparation Location Latitude")
    library_preparation_location_latitude_unit: Optional[str] = Field(None, alias="Library Preparation Location Latitude Unit")
    library_preparation_date: Optional[str] = Field(None, alias="Library Preparation Date")
    library_preparation_date_unit: Optional[str] = Field(None, alias="Library Preparation Date Unit")
    sequencing_location: Optional[str] = Field(None, alias="Sequencing Location")
    sequencing_location_longitude: Optional[Union[float, str]] = Field(None, alias="Sequencing Location Longitude")
    sequencing_location_longitude_unit: Optional[str] = Field(None, alias="Sequencing Location Longitude Unit")
    sequencing_location_latitude: Optional[Union[float, str]] = Field(None, alias="Sequencing Location Latitude")
    sequencing_location_latitude_unit: Optional[str] = Field(None, alias="Sequencing Location Latitude Unit")
    sequencing_date: Optional[str] = Field(None, alias="Sequencing Date")
    sequencing_date_unit: Optional[str] = Field(None, alias="Sequencing Date Unit")


class Config:
        populate_by_name = True
        validate_default = True
        validate_assignment = True
        extra = "forbid"


