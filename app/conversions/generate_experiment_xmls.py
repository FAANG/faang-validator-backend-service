from lxml import etree
from typing import Dict, Any, Optional
import uuid
import datetime
import re


def get_xml_files(json_data: Dict[str, Any], submission_id: Optional[str] = None, action: str = "submission"):
    if submission_id:
        experiment_filename = f"{submission_id}_experiment.xml"
        run_filename = f"{submission_id}_run.xml"
        study_filename = f"{submission_id}_study.xml"
        submission_filename = f"{submission_id}_submission.xml"
    else:
        unique_id = str(uuid.uuid4())
        experiment_filename = f"{unique_id}_experiment.xml"
        run_filename = f"{unique_id}_run.xml"
        study_filename = f"{unique_id}_study.xml"
        submission_filename = f"{unique_id}_submission.xml"
    
    # Generate XML files
    experiment_result = generate_experiment_xml(json_data, experiment_filename)
    if experiment_result.startswith('Error:'):
        return experiment_result, None, None, None
    
    run_result = generate_run_xml(json_data, run_filename)
    if run_result.startswith('Error:'):
        return experiment_result, run_result, None, None
    
    study_result = generate_study_xml(json_data, study_filename)
    if study_result.startswith('Error:'):
        return experiment_result, run_result, study_result, None
    
    submission_result = generate_submission_xml(json_data, submission_filename, action=action)
    if submission_result.startswith('Error:'):
        return experiment_result, run_result, study_result, submission_result
    
    return experiment_result, run_result, study_result, submission_result


def convert_unit_fields_to_dicts(model: Dict[str, Any]) -> Dict[str, Any]:
    # unit field pairs (main_field, unit_field)
    UNIT_FIELD_PAIRS = [
        ("Sampling to Preparation Interval", "Unit"),
        ("Library Preparation Location Longitude", "Library Preparation Location Longitude Unit"),
        ("Library Preparation Location Latitude", "Library Preparation Location Latitude Unit"),
        ("Library Preparation Date", "Library Preparation Date Unit"),
        ("Sequencing Location Longitude", "Sequencing Location Longitude Unit"),
        ("Sequencing Location Latitude", "Sequencing Location Latitude Unit"),
        ("Sequencing Date", "Sequencing Date Unit"),
    ]

    converted = dict(model)

    for main_field, unit_field in UNIT_FIELD_PAIRS:
        if main_field in converted and unit_field in converted:
            value = converted[main_field]
            units = converted[unit_field]

            converted[main_field] = {
                "value": value,
                "units": units
            }

            del converted[unit_field]

    return converted

def convert_ontology_fields_to_dicts(model: Dict[str, Any]) -> Dict[str, Any]:
    # ontology field pairs (main_field, term_field)
    ONTOLOGY_FIELD_PAIRS = [
        ("Experiment Target", "Term Source ID"),
        ("ChIP Target", "ChIP Target Term Source ID"),
    ]

    converted = dict(model)

    for main_field, term_field in ONTOLOGY_FIELD_PAIRS:
        if main_field in converted and term_field in converted:
            # get the text and term values
            text_value = converted[main_field]
            term_value = converted[term_field]

            converted[main_field] = {
                "text": text_value,
                "term": term_value
            }

            del converted[term_field]

    return converted

def generate_experiment_xml(json_data: Dict[str, Any], output_filename: Optional[str] = None) -> str:
    try:
        # Get experiment_ena data (ENA-specific metadata)
        experiment_results = json_data.get('experiment_results', {})
        ena_data = experiment_results.get('experiment_ena', {})
        ena_records = ena_data.get('valid', []) if isinstance(ena_data, dict) else []
        
        if not ena_records:
            return 'Error: No valid experiment_ena records found in JSON data'
        
        # Create XML structure
        experiment_set = etree.Element('EXPERIMENT_SET')
        experiment_xml = etree.ElementTree(experiment_set)
        
        # Process each experiment_ena record
        for record in ena_records:
            model = record.get('model', {})
            
            # Extract ENA fields
            alias = model.get('Experiment Alias')
            if not alias:
                return 'Error: Missing Experiment Alias in experiment_ena record'
            
            title = model.get('Title')
            study_ref = model.get('Study Ref')
            if not study_ref:
                return f'Error: Missing Study Ref in experiment {alias}'
            
            design_description = model.get('Design Description')
            if not design_description:
                return f'Error: Missing Design Description in experiment {alias}'
            
            sample_descriptor = model.get('Sample Descriptor')
            if not sample_descriptor:
                return f'Error: Missing Sample Descriptor in experiment {alias}'
            
            library_name = model.get('Library Name')
            library_strategy = model.get('Library Strategy')
            if not library_strategy:
                return f'Error: Missing Library Strategy in experiment {alias}'
            
            library_source = model.get('Library Source')
            if not library_source:
                return f'Error: Missing Library Source in experiment {alias}'
            
            library_selection = model.get('Library Selection')
            if not library_selection:
                return f'Error: Missing Library Selection in experiment {alias}'
            
            library_layout = model.get('Library Layout')
            if not library_layout:
                return f'Error: Missing Library Layout in experiment {alias}'
            
            nominal_length = model.get('Nominal Length')
            library_construction_protocol = model.get('Library Construction Protocol')
            platform = model.get('Platform')
            if not platform:
                return f'Error: Missing Platform in experiment {alias}'
            
            instrument_model = model.get('Instrument Model')
            
            # Create EXPERIMENT element
            experiment_elt = etree.SubElement(experiment_set, 'EXPERIMENT', alias=alias)
            
            if title and title.strip():
                etree.SubElement(experiment_elt, 'TITLE').text = title
            
            etree.SubElement(experiment_elt, 'STUDY_REF', refname=study_ref)
            
            # Design section
            design_elt = etree.SubElement(experiment_elt, 'DESIGN')
            etree.SubElement(design_elt, 'DESIGN_DESCRIPTION').text = design_description
            etree.SubElement(design_elt, 'SAMPLE_DESCRIPTOR', refname=sample_descriptor)
            
            # Library descriptor
            library_descriptor_elt = etree.SubElement(design_elt, 'LIBRARY_DESCRIPTOR')
            
            if library_name and library_name.strip():
                etree.SubElement(library_descriptor_elt, 'LIBRARY_NAME').text = library_name
            
            etree.SubElement(library_descriptor_elt, 'LIBRARY_STRATEGY').text = library_strategy
            etree.SubElement(library_descriptor_elt, 'LIBRARY_SOURCE').text = library_source
            etree.SubElement(library_descriptor_elt, 'LIBRARY_SELECTION').text = library_selection
            
            # Library layout
            library_layout_elt = etree.SubElement(library_descriptor_elt, 'LIBRARY_LAYOUT')
            if nominal_length and str(nominal_length).strip() and nominal_length != "":
                try:
                    nominal_length_int = int(float(nominal_length))
                    etree.SubElement(library_layout_elt, library_layout, 
                                   NOMINAL_LENGTH=str(nominal_length_int))
                except (ValueError, TypeError):
                    etree.SubElement(library_layout_elt, library_layout)
            else:
                etree.SubElement(library_layout_elt, library_layout)
            
            if library_construction_protocol and library_construction_protocol.strip():
                etree.SubElement(library_descriptor_elt, 
                               'LIBRARY_CONSTRUCTION_PROTOCOL').text = library_construction_protocol
            
            # Platform
            platform_elt = etree.SubElement(experiment_elt, 'PLATFORM')
            platform_desc_elt = etree.SubElement(platform_elt, platform)
            if instrument_model and instrument_model.strip():
                etree.SubElement(platform_desc_elt, 'INSTRUMENT_MODEL').text = instrument_model
            
            # FAANG attributes - find matching FAANG experiment
            faang_experiment = find_faang_experiment(experiment_results, alias)
            if not faang_experiment:
                return f"Error: No FAANG data found for experiment {alias}"
            
            # Add FAANG attributes
            experiment_attributes_elt = etree.SubElement(experiment_elt, 'EXPERIMENT_ATTRIBUTES')
            parse_faang_experiment(faang_experiment, experiment_attributes_elt)
        
        # Generate output filename if not provided
        if output_filename is None:
            output_filename = f"{uuid.uuid4()}_experiment.xml"
        
        # Write XML file
        experiment_xml.write(
            output_filename,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )
        
        return output_filename
    
    except KeyError as e:
        return f'Error: Missing required key in JSON data: {str(e)}'
    except Exception as e:
        return f'Error: Failed to generate experiment XML: {str(e)}'


def find_faang_experiment(experiment_results: Dict[str, Any], experiment_alias: str) -> Optional[Dict[str, Any]]:
    """
    Find the FAANG experiment record matching the given experiment alias.
    
    Args:
        experiment_results: All experiment validation results
        experiment_alias: The experiment alias to search for
    
    Returns:
        Dict containing the FAANG experiment data, or None if not found
    """
    # Check all experiment types
    experiment_types = [
        'atac-seq', 'bs-seq', 'cage-seq', 'chip-seq dna-binding proteins', 
        'chip-seq input dna', 'dnase-seq', 'em-seq', 'hi-c', 'rna-seq', 
        'scrna-seq', 'snatac-seq', 'wgs'
    ]
    
    for exp_type in experiment_types:
        if exp_type not in experiment_results:
            continue
        
        exp_data = experiment_results[exp_type]
        if not isinstance(exp_data, dict):
            continue
        
        valid_records = exp_data.get('valid', [])
        for record in valid_records:
            model = record.get('model', {})
            if model.get('Experiment Alias') == experiment_alias:
                # Return both model and experiment type
                return {
                    'model': model,
                    'experiment_type': exp_type
                }
    
    return None


def parse_faang_experiment(faang_data: Dict[str, Any], experiment_attributes_elt):
    model = faang_data.get('model', {})

    model = convert_ontology_fields_to_dicts(model)
    model = convert_unit_fields_to_dicts(model)
    
    # Exclude these fields from attributes (structural fields)
    excluded_fields = {'Experiment Alias', 'Sample Descriptor'}
    
    for field_name, field_value in model.items():
        if field_name in excluded_fields or field_value is None:
            continue
        
        # Convert field name to tag format (Title Case with spaces)
        tag_name = field_name
        
        # Handle different field value types
        if isinstance(field_value, list):
            # Handle list fields (e.g., Secondary Project)
            for item in field_value:
                if item and (isinstance(item, str) and item.strip() or item):
                    experiment_attribute_elt = etree.SubElement(
                        experiment_attributes_elt, 'EXPERIMENT_ATTRIBUTE')
                    etree.SubElement(experiment_attribute_elt, 'TAG').text = tag_name
                    etree.SubElement(experiment_attribute_elt, 'VALUE').text = str(item)
        elif isinstance(field_value, dict):
            # ontology term fields (e.g., chip target, Experiment Target)
            text_value = field_value.get('text', '')
            term_value = field_value.get('term', '')

            value = field_value.get('value', '')
            units = field_value.get('units', '')

            if text_value:
                final_value = text_value
            elif value:
                final_value = value
            else:
                continue

            experiment_attribute_elt = etree.SubElement(
                experiment_attributes_elt, 'EXPERIMENT_ATTRIBUTE')
            etree.SubElement(experiment_attribute_elt, 'TAG').text = tag_name
            etree.SubElement(experiment_attribute_elt, 'VALUE').text = str(final_value)

            if units:
                etree.SubElement(experiment_attribute_elt, 'UNITS').text = str(units)

        else:
            # Handle simple string/numeric fields
            if field_value and (isinstance(field_value, str) and field_value.strip() or field_value):
                experiment_attribute_elt = etree.SubElement(
                    experiment_attributes_elt, 'EXPERIMENT_ATTRIBUTE')
                etree.SubElement(experiment_attribute_elt, 'TAG').text = tag_name
                etree.SubElement(experiment_attribute_elt, 'VALUE').text = str(field_value)


def add_leading_zero(date_item: int) -> str:
    """Add leading zero if date is just one number."""
    if date_item < 10:
        return f"0{date_item}"
    else:
        return str(date_item)


def generate_run_xml(json_data: Dict[str, Any], output_filename: Optional[str] = None) -> str:
    """
    Generate run XML file from JSON data.
    
    Args:
        json_data: Dictionary containing run validation results
        output_filename: Optional filename for the XML file
    
    Returns:
        str: Path to the generated XML file, or 'Error: ...' if there was an error
    """
    try:
        # Get run data
        metadata_results = json_data.get('metadata_results', {})
        run_data = metadata_results.get('run', {})
        run_records = run_data.get('valid', []) if isinstance(run_data, dict) else []
        
        if not run_records:
            return 'Error: No valid run records found in JSON data'
        
        # Create XML structure
        run_set = etree.Element('RUN_SET')
        run_xml = etree.ElementTree(run_set)
        
        # Process each run record
        for record in run_records:
            model = record.get('model', {})
            
            # Extract fields
            run_alias = model.get('Alias')
            if not run_alias:
                return 'Error: Missing Alias in run record'
            
            run_center = model.get('Run Center')
            if not run_center:
                return f'Error: Missing Run Center in run {run_alias}'
            
            run_date = model.get('Run Date')
            experiment_ref = model.get('Experiment Ref')
            if not experiment_ref:
                return f'Error: Missing Experiment Ref in run {run_alias}'
            
            filename = model.get('Filename')
            if not filename:
                return f'Error: Missing Filename in run {run_alias}'
            
            filetype = model.get('Filetype')
            if not filetype:
                return f'Error: Missing Filetype in run {run_alias}'
            
            checksum_method = model.get('Checksum Method')
            if not checksum_method:
                return f'Error: Missing Checksum Method in run {run_alias}'
            
            checksum = model.get('Checksum')
            if not checksum:
                return f'Error: Missing Checksum in run {run_alias}'
            
            # Check for paired-end data
            filename_pair = model.get('Filename Pair')
            filetype_pair = model.get('Filetype Pair')
            checksum_method_pair = model.get('Checksum Method Pair')
            checksum_pair = model.get('Checksum Pair')
            
            paired = all([filename_pair, filetype_pair, checksum_method_pair, checksum_pair])
            
            # Parse run date if present
            run_date_iso = None
            if run_date and run_date.strip():
                try:
                    # Try different date formats
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', run_date):
                        run_date_iso = datetime.datetime.strptime(run_date, '%Y-%m-%d').isoformat()
                    elif re.match(r'^\d{4}-\d{2}$', run_date):
                        run_date_iso = datetime.datetime.strptime(run_date, '%Y-%m').isoformat()
                    elif re.match(r'^\d{4}$', run_date):
                        run_date_iso = datetime.datetime.strptime(run_date, '%Y').isoformat()
                except (ValueError, AttributeError):
                    # If parsing fails, skip the date
                    pass
            
            # Create RUN element
            if run_date_iso:
                run_elt = etree.SubElement(
                    run_set, 'RUN', 
                    alias=run_alias, 
                    run_center=run_center,
                    run_date=run_date_iso
                )
            else:
                run_elt = etree.SubElement(
                    run_set, 'RUN', 
                    alias=run_alias, 
                    run_center=run_center
                )
            
            etree.SubElement(run_elt, 'EXPERIMENT_REF', refname=experiment_ref)
            
            # Data block with files
            data_block_elt = etree.SubElement(run_elt, 'DATA_BLOCK')
            files_elt = etree.SubElement(data_block_elt, 'FILES')
            
            # Add first file
            etree.SubElement(
                files_elt, 'FILE',
                filename=filename,
                filetype=filetype,
                checksum_method=checksum_method,
                checksum=checksum
            )
            
            # Add second file if paired
            if paired:
                etree.SubElement(
                    files_elt, 'FILE',
                    filename=filename_pair,
                    filetype=filetype_pair,
                    checksum_method=checksum_method_pair,
                    checksum=checksum_pair
                )
        
        # Generate output filename if not provided
        if output_filename is None:
            output_filename = f"{uuid.uuid4()}_run.xml"
        
        # Write XML file
        run_xml.write(
            output_filename,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )
        
        return output_filename
    
    except KeyError as e:
        return f'Error: Missing required key in JSON data: {str(e)}'
    except Exception as e:
        return f'Error: Failed to generate run XML: {str(e)}'


def generate_study_xml(json_data: Dict[str, Any], output_filename: Optional[str] = None) -> str:
    """
    Generate study XML file from JSON data.
    
    Args:
        json_data: Dictionary containing study validation results
        output_filename: Optional filename for the XML file
    
    Returns:
        str: Path to the generated XML file, or 'Error: ...' if there was an error
    """
    try:
        # Get study data
        metadata_results = json_data.get('metadata_results', {})
        study_data = metadata_results.get('study', {})
        study_records = study_data.get('valid', []) if isinstance(study_data, dict) else []
        
        if not study_records:
            return 'Error: No valid study records found in JSON data'
        
        # Create XML structure
        study_set = etree.Element('STUDY_SET')
        study_xml = etree.ElementTree(study_set)
        
        # Process each study record
        for record in study_records:
            model = record.get('model', {})
            
            # Extract fields
            study_alias = model.get('Study Alias')
            if not study_alias:
                return 'Error: Missing Study Alias in study record'
            
            study_title = model.get('Study Title')
            if not study_title:
                return f'Error: Missing Study Title in study {study_alias}'
            
            study_type = model.get('Study Type')
            if not study_type:
                return f'Error: Missing Study Type in study {study_alias}'
            
            study_abstract = model.get('Study Abstract')
            
            # Create STUDY element
            study_elt = etree.SubElement(study_set, 'STUDY', alias=study_alias)
            descriptor_elt = etree.SubElement(study_elt, 'DESCRIPTOR')
            
            etree.SubElement(descriptor_elt, 'STUDY_TITLE').text = study_title
            etree.SubElement(descriptor_elt, 'STUDY_TYPE', existing_study_type=study_type)
            
            if study_abstract and study_abstract.strip():
                etree.SubElement(descriptor_elt, 'STUDY_ABSTRACT').text = study_abstract
        
        # Generate output filename if not provided
        if output_filename is None:
            output_filename = f"{uuid.uuid4()}_study.xml"
        
        # Write XML file
        study_xml.write(
            output_filename,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )
        
        return output_filename
    
    except KeyError as e:
        return f'Error: Missing required key in JSON data: {str(e)}'
    except Exception as e:
        return f'Error: Failed to generate study XML: {str(e)}'


def generate_submission_xml(json_data: Dict[str, Any], output_filename: Optional[str] = None,
                           action: str = "submission") -> str:
    """
    Generate submission XML file from JSON data.
    
    Args:
        json_data: Dictionary containing submission data
        output_filename: Optional filename for the XML file
        action: 'submission' (default) or 'update'
    
    Returns:
        str: Path to the generated XML file, or 'Error: ...' if there was an error
    """
    try:
        # Get submission data
        metadata_results = json_data.get('metadata_results', {})
        submission_data = metadata_results.get('submission', {})
        
        if not submission_data:
            submission_data = json_data.get('submission', {})
        
        submission_records = submission_data.get('valid', []) if isinstance(submission_data, dict) else []
        
        if not submission_records:
            return 'Error: No valid submission records found in JSON data'
        
        # Create XML structure
        submission_set = etree.Element('SUBMISSION_SET')
        submission_xml = etree.ElementTree(submission_set)
        
        # Process each submission record
        for record in submission_records:
            model = record.get('model', {})
            alias = model.get('Alias')
            
            if not alias:
                alias = record.get('alias')
                if not alias:
                    return 'Error: Missing Alias in submission record'
            
            # Create SUBMISSION element
            submission_elt = etree.SubElement(submission_set, 'SUBMISSION', alias=alias)
            actions_elt = etree.SubElement(submission_elt, 'ACTIONS')
            action_elt = etree.SubElement(actions_elt, 'ACTION')
            
            if action == 'update':
                etree.SubElement(action_elt, 'MODIFY')
            else:
                # For public submission, add ADD and RELEASE actions
                etree.SubElement(action_elt, 'ADD')
                # Release immediately
                action_elt = etree.SubElement(actions_elt, 'ACTION')
                etree.SubElement(action_elt, 'RELEASE')
        
        # Generate output filename if not provided
        if output_filename is None:
            output_filename = f"{uuid.uuid4()}_submission.xml"
        
        # Write XML file
        submission_xml.write(
            output_filename,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )
        
        return output_filename
    
    except KeyError as e:
        return f'Error: Missing required key in JSON data: {str(e)}'
    except Exception as e:
        return f'Error: Failed to generate submission XML: {str(e)}'
