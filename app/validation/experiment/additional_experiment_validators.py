from typing import Type
from pydantic import BaseModel
from app.validation.experiment.base_experiment_validator import BaseExperimentValidator
from app.validation.generic_validator_classes import OntologyValidator
from app.rulesets_pydantics.experiment.bs_seq_ruleset import BSSeqExperiment
from app.rulesets_pydantics.experiment.cage_seq_ruleset import CAGESeqExperiment
from app.rulesets_pydantics.experiment.dnase_seq_ruleset import DNaseSeqExperiment
from app.rulesets_pydantics.experiment.em_seq_ruleset import EMSeqExperiment
from app.rulesets_pydantics.experiment.hi_c_ruleset import HiCExperiment
from app.rulesets_pydantics.experiment.rna_seq_ruleset import RNASeqExperiment
from app.rulesets_pydantics.experiment.scrna_seq_ruleset import scRNASeqExperiment
from app.rulesets_pydantics.experiment.scatac_seq_ruleset import scATACSeqExperiment
from app.rulesets_pydantics.experiment.wgs_ruleset import WGSExperiment


class BSSeqValidator(BaseExperimentValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return BSSeqExperiment
    
    def get_experiment_type_name(self) -> str:
        return "bs-seq"


class CAGESeqValidator(BaseExperimentValidator):
    
    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return CAGESeqExperiment
    
    def get_experiment_type_name(self) -> str:
        return "cage-seq"


class DNaseSeqValidator(BaseExperimentValidator):
    
    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return DNaseSeqExperiment
    
    def get_experiment_type_name(self) -> str:
        return "dnase-seq"


class EMSeqValidator(BaseExperimentValidator):
    
    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return EMSeqExperiment
    
    def get_experiment_type_name(self) -> str:
        return "em-seq"


class HiCValidator(BaseExperimentValidator):
    
    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return HiCExperiment
    
    def get_experiment_type_name(self) -> str:
        return "hi-c"


class RNASeqValidator(BaseExperimentValidator):
    
    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return RNASeqExperiment
    
    def get_experiment_type_name(self) -> str:
        return "rna-seq"


class scRNASeqValidator(BaseExperimentValidator):
    
    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return scRNASeqExperiment
    
    def get_experiment_type_name(self) -> str:
        return "scrna-seq"


class scATACSeqValidator(BaseExperimentValidator):
    
    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return scATACSeqExperiment
    
    def get_experiment_type_name(self) -> str:
        return "snatac-seq"


class WGSValidator(BaseExperimentValidator):
    
    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return WGSExperiment
    
    def get_experiment_type_name(self) -> str:
        return "wgs"
