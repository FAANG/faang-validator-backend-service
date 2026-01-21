from typing import Type, Dict, List
from pydantic import BaseModel
from app.validation.experiment.base_experiment_validator import BaseExperimentValidator
from app.validation.generic_validator_classes import OntologyValidator
from app.rulesets_pydantics.experiment.experiment_chip_seq_ruleset import (
    ChIPSeqDNABindingProteinsExperiment,
    ChIPSeqInputDNAExperiment
)


class ChIPSeqDNABindingProteinsValidator(BaseExperimentValidator):

    def __init__(self, ontology_validator=None, ena_cache: Dict[str, bool] = None):
        super().__init__(ontology_validator)
        self.ena_cache = ena_cache or {}

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return ChIPSeqDNABindingProteinsExperiment
    
    def get_experiment_type_name(self) -> str:
        return "chip-seq dna-binding proteins"
    
    def _get_relationship_errors(self, all_experiments: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
        relationship_errors = {}
        
        # ChIP-seq DNA-binding proteins experiments
        dna_binding_experiments = all_experiments.get('chip-seq dna-binding proteins', [])
        input_dna_experiments = all_experiments.get('chip-seq input dna', [])
        
        input_dna_aliases = set()
        for exp in input_dna_experiments:
            alias = exp.get('Experiment Alias', '')
            if alias:
                input_dna_aliases.add(alias)
        
        for exp in dna_binding_experiments:
            sample_descriptor = exp.get('Sample Descriptor',
                               exp.get('Experiment Alias', 'unknown'))
            control_exp = exp.get('Control Experiment')
            
            if not control_exp or control_exp in [
                "not applicable", 
                "not collected", 
                "not provided", 
                "restricted access"
            ]:
                continue
            
            if control_exp in input_dna_aliases:
                continue
            
            if self.check_control_in_ena(control_exp):
                continue
            
            if sample_descriptor not in relationship_errors:
                relationship_errors[sample_descriptor] = []
            relationship_errors[sample_descriptor].append(
                f"Control experiment '{control_exp}' not found in this submission or in ENA"
            )
        
        return relationship_errors

    def check_control_in_ena(self, experiment_alias: str) -> bool:
        if experiment_alias in self.ena_cache:
            return self.ena_cache[experiment_alias]
        return False


class ChIPSeqInputDNAValidator(BaseExperimentValidator):

    def _initialize_validators(self):
        if self.ontology_validator is None:
            self.ontology_validator = OntologyValidator(cache_enabled=True)
    
    def get_model_class(self) -> Type[BaseModel]:
        return ChIPSeqInputDNAExperiment
    
    def get_experiment_type_name(self) -> str:
        return "chip-seq input dna"
