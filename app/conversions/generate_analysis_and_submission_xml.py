from lxml import etree
from typing import Dict, Any, Optional
import uuid


def get_xml_files(json_data: Dict[str, Any], output_filename: Optional[str] = None):

    analysis_xml = generate_analysis_xml(json_data,
                                         output_filename)


    submission_xml = generate_submission_xml(json_data,
                                         output_filename)
    return analysis_xml, submission_xml


def generate_analysis_xml(json_data: Dict[str, Any], output_filename: Optional[str] = None) -> str:
    """
    Generate analysis XML file from JSON data.

    Args:
        json_data: Dictionary containing 'ena' and 'faang' keys with validation results.
                  Expected structure:
                  {
                      'ena': {
                          'valid': [
                              {
                                  'model': {
                                      'Alias': '...',
                                      'Analysis Type': '...',
                                      'Study': '...',
                                      'Title': '...',  # optional
                                      'Description': '...',  # optional
                                      'Samples': [...],  # optional
                                      'Experiments': [...],  # optional
                                      'Runs': [...],  # optional
                                      'Related Analyses': [...],  # optional
                                      'File Names': [...],
                                      'File Types': [...],
                                      'Checksum Methods': [...],
                                      'Checksums': [...],
                                      'Analysis Center': '...',  # optional
                                      'Analysis Date': '...',  # optional
                                      'Unit': '...',  # optional
                                  }
                              }
                          ]
                      },
                      'faang': {
                          'valid': [
                              {
                                  'model': {
                                      'Alias': '...',
                                      'Project': '...',
                                      'Assay Type': '...',
                                      'Analysis Protocol': '...',
                                      'Secondary Project': [...],  # optional
                                      'Analysis Code': '...',  # optional
                                      'Reference Genome': '...',  # optional
                                  }
                              }
                          ]
                      }
                  }
        output_filename: Optional filename for the XML file. If not provided,
                        generates a UUID-based filename.

    Returns:
        str: Path to the generated XML file, or 'Error: ...' if there was an error.
    """
    try:

        ena_data = json_data.get('analysis_results', {}).get('ena', {})
        faang_data = json_data.get('analysis_results', {}).get('ena', {})

        ena_records = ena_data.get('valid', []) if isinstance(ena_data, dict) else []
        faang_records = faang_data.get('valid', []) if isinstance(faang_data, dict) else []

        if not ena_records:
            return 'Error: No valid ENA records found in JSON data'

        if not faang_records:
            return 'Error: No valid FAANG records found in JSON data'

        if len(ena_records) != len(faang_records):
            return f'Error: Mismatch in number of records - ENA: {len(ena_records)}, FAANG: {len(faang_records)}'

        # Create XML structure
        analysis_set = etree.Element('ANALYSIS_SET')
        analysis_xml = etree.ElementTree(analysis_set)

        number_of_records = len(ena_records)

        for record_number in range(number_of_records):
            # Get records and extract model data
            ena_record = ena_records[record_number]
            faang_record = faang_records[record_number]

            # Get model dictionaries
            ena_model = ena_record.get('model', {})
            faang_model = faang_record.get('model', {})

            # Extract ENA fields from model
            alias = ena_model.get('Alias')
            if not alias:
                return f'Error: Missing Alias in ENA record {record_number}'

            analysis_type = ena_model.get('Analysis Type')
            if not analysis_type:
                return f'Error: Missing Analysis Type in ENA record {record_number}'

            study = ena_model.get('Study')
            if not study:
                return f'Error: Missing Study in ENA record {record_number}'

            title = ena_model.get('Title')
            description = ena_model.get('Description')
            samples = ena_model.get('Samples', [])
            experiments = ena_model.get('Experiments', [])
            runs = ena_model.get('Runs', [])
            related_analyses = ena_model.get('Related Analyses')

            file_names = ena_model.get('File Names', [])
            file_types = ena_model.get('File Types', [])
            checksum_methods = ena_model.get('Checksum Methods', [])
            checksums = ena_model.get('Checksums', [])

            if len(file_names) != len(file_types) or len(file_names) != len(checksum_methods) or len(file_names) != len(
                    checksums):
                return f'Error: Mismatch in file arrays length in ENA record {record_number}'

            analysis_center = ena_model.get('Analysis Center')
            analysis_date = ena_model.get('Analysis Date')
            analysis_date_unit = ena_model.get('Unit')

            # Extract FAANG fields from model
            faang_alias = faang_model.get('Alias')
            if not faang_alias:
                return f'Error: Missing Alias in FAANG record {record_number}'

            if faang_alias != alias:
                return f'Error: Analysis alias is not consistent between ENA and FAANG records - ENA: {alias}, FAANG: {faang_alias}'

            project = faang_model.get('Project')
            if not project:
                return f'Error: Missing Project in FAANG record {record_number}'

            secondary_project = faang_model.get('Secondary Project')
            assay_type = faang_model.get('Assay Type')
            if not assay_type:
                return f'Error: Missing Assay Type in FAANG record {record_number}'

            analysis_protocol = faang_model.get('Analysis Protocol')
            if not analysis_protocol:
                return f'Error: Missing Analysis Protocol in FAANG record {record_number}'

            analysis_code = faang_model.get('Analysis Code')
            reference_genome = faang_model.get('Reference Genome')

            # Create ANALYSIS element
            analysis_elt = etree.SubElement(analysis_set, 'ANALYSIS', alias=alias)

            # Add title if present
            if title and title.strip():
                etree.SubElement(analysis_elt, 'TITLE').text = title

            # Add description if present
            if description and description.strip():
                etree.SubElement(analysis_elt, 'DESCRIPTION').text = description

            # Add study reference
            etree.SubElement(analysis_elt, 'STUDY_REF', accession=study)

            # Add sample references if present
            if samples:
                for sample in samples:
                    if sample and (isinstance(sample, str) and sample.strip() or sample):
                        sample_value = sample if isinstance(sample, str) else str(sample)
                        etree.SubElement(analysis_elt, 'SAMPLE_REF', accession=sample_value)

            # Add experiment references if present
            if experiments:
                for experiment in experiments:
                    if experiment and (isinstance(experiment, str) and experiment.strip() or experiment):
                        exp_value = experiment if isinstance(experiment, str) else str(experiment)
                        etree.SubElement(analysis_elt, 'EXPERIMENT_REF', accession=exp_value)

            # Add run references if present
            if runs:
                for run in runs:
                    if run and (isinstance(run, str) and run.strip() or run):
                        run_value = run if isinstance(run, str) else str(run)
                        etree.SubElement(analysis_elt, 'RUN_REF', accession=run_value)

            # Add related analysis references if present
            if related_analyses:
                if isinstance(related_analyses, list):
                    for analysis in related_analyses:
                        if analysis and (isinstance(analysis, str) and analysis.strip() or analysis):
                            analysis_value = analysis if isinstance(analysis, str) else str(analysis)
                            etree.SubElement(analysis_elt, 'ANALYSIS_REF', accession=analysis_value)
                elif isinstance(related_analyses, str) and related_analyses.strip():
                    etree.SubElement(analysis_elt, 'ANALYSIS_REF', accession=related_analyses)

            # Add analysis type
            analysis_type_elt = etree.SubElement(analysis_elt, 'ANALYSIS_TYPE')
            etree.SubElement(analysis_type_elt, analysis_type)

            # Add files
            files_elt = etree.SubElement(analysis_elt, 'FILES')
            for index, file_name in enumerate(file_names):
                filename = file_name if isinstance(file_name, str) else str(file_name)
                filetype = file_types[index] if isinstance(file_types[index], str) else str(file_types[index])
                checksum_method = checksum_methods[index] if isinstance(checksum_methods[index], str) else str(
                    checksum_methods[index])
                checksum = checksums[index] if isinstance(checksums[index], str) else str(checksums[index])

                etree.SubElement(
                    files_elt, 'FILE',
                    filename=filename,
                    filetype=filetype,
                    checksum_method=checksum_method,
                    checksum=checksum
                )

            # Add analysis attributes
            analysis_attributes_elt = etree.SubElement(analysis_elt, 'ANALYSIS_ATTRIBUTES')

            # Project (required)
            analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
            etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Project'
            etree.SubElement(analysis_attribute_elt, 'VALUE').text = project

            # Secondary Project (optional)
            if secondary_project is not None and secondary_project != "":
                if isinstance(secondary_project, list):
                    for item in secondary_project:
                        if item and (isinstance(item, str) and item.strip() or item):
                            item_value = item if isinstance(item, str) else str(item)
                            analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
                            etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Secondary Project'
                            etree.SubElement(analysis_attribute_elt, 'VALUE').text = item_value
                elif isinstance(secondary_project, str) and secondary_project.strip():
                    analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
                    etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Secondary Project'
                    etree.SubElement(analysis_attribute_elt, 'VALUE').text = secondary_project

            # Assay Type (required)
            analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
            etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Assay Type'
            etree.SubElement(analysis_attribute_elt, 'VALUE').text = assay_type

            # Analysis Protocol (required)
            analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
            etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Analysis Protocol'
            etree.SubElement(analysis_attribute_elt, 'VALUE').text = analysis_protocol

            # Analysis code (optional)
            if analysis_code and analysis_code.strip():
                analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
                etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Analysis code'
                etree.SubElement(analysis_attribute_elt, 'VALUE').text = analysis_code

            # Reference genome (optional)
            if reference_genome and reference_genome.strip():
                analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
                etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Reference genome'
                etree.SubElement(analysis_attribute_elt, 'VALUE').text = reference_genome

            # Analysis center (optional)
            if analysis_center and analysis_center.strip():
                analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
                etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Analysis center'
                etree.SubElement(analysis_attribute_elt, 'VALUE').text = analysis_center

            # Analysis date (optional)
            if analysis_date and analysis_date.strip():
                analysis_attribute_elt = etree.SubElement(analysis_attributes_elt, 'ANALYSIS_ATTRIBUTE')
                etree.SubElement(analysis_attribute_elt, 'TAG').text = 'Analysis date'
                etree.SubElement(analysis_attribute_elt, 'VALUE').text = analysis_date
                if analysis_date_unit and analysis_date_unit.strip():
                    etree.SubElement(analysis_attribute_elt, 'UNITS').text = analysis_date_unit

        # Generate output filename if not provided
        if output_filename is None:
            output_filename = f"{uuid.uuid4()}_analysis.xml"

        # Write XML file
        analysis_xml.write(
            output_filename,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )

        return output_filename

    except KeyError as e:
        return f'Error: Missing required key in JSON data: {str(e)}'
    except Exception as e:
        return f'Error: Failed to generate analysis XML: {str(e)}'


def generate_submission_xml(json_data: Dict[str, Any], output_filename: Optional[str] = None,
                            action: str = "submission") -> str:
    """
    Generate submission XML file from JSON data.

    Args:
        json_data: Dictionary containing submission data. Expected structure:
                  {
                      'metadata_results': {
                          'submission': {
                              'valid': [
                                  {
                                      'model': {
                                          'Alias': 'submission_alias'
                                      }
                                  }
                              ]
                          }
                      }
                  }
                  OR directly:
                  {
                      'submission': {
                          'valid': [
                              {
                                  'model': {
                                      'Alias': 'submission_alias'
                                  }
                              }
                          ]
                      }
                  }
        output_filename: Optional filename for the XML file. If not provided,
                        generates a UUID-based filename.
        action: 'submission' (default) or 'update'
        room_id: Optional room ID for file naming. If not provided, uses UUID.

    Returns:
        str: Path to the generated XML file, or 'Error: ...' if there was an error.
    """
    try:
        # Get submission data from JSON structure
        # Try metadata_results.submission first, then direct

        if 'metadata_results' in json_data:
            submission_data = json_data.get('metadata_results', {}).get('submission', {})
        else:
            submission_data = json_data.get('submission', {})

        if not submission_data:
            return 'Error: No submission data found in JSON. Expected "metadata_results.submission" or "submission" key'

        submission_records = submission_data.get('valid', [])

        if not submission_records:
            return 'Error: No valid submission records found in JSON data'

        # Create XML structure
        submission_set = etree.Element('SUBMISSION_SET')
        submission_xml = etree.ElementTree(submission_set)

        # Process each submission record
        for record in submission_records:
            # Get model data
            model = record.get('model', {})
            alias = model.get('Alias')

            if not alias:
                # Try getting alias from record directly if not in model
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
                # For submission (public), add ADD and RELEASE actions
                etree.SubElement(action_elt, 'ADD')
                # Release immediately in case of public submission
                action_elt = etree.SubElement(actions_elt, 'ACTION')
                etree.SubElement(action_elt, 'RELEASE')

            # Generate output filename if not provided

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

