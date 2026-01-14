from typing import Type
from pydantic import BaseModel
from validation.experiment.base_experiment_validator import BaseExperimentValidator
from validation.generic_validator_classes import OntologyValidator
from rulesets_pydantics.experiment.atac_seq_ruleset import ATACSeqExperiment


class ATACSeqValidator(BaseExperimentValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return ATACSeqExperiment
    
    def get_experiment_type_name(self) -> str:
        return "atac-seq"
