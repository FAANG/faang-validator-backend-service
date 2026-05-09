"""
ENA-required field resolution for BioSamples submissions.

When an experiment is submitted to ENA referencing a BioSample, ENA's
submission validator enforces the INSDC minimum sample checklist on every
referenced sample. Two of those required fields - `collection date` and
`geographic location (country and/or sea)` - use names that don't match the
FAANG-flavoured names the per-sample validators emit (`specimen collection
date`, `geographic location`).

This module bridges that gap. After the per-sample `export_to_biosample_format`
calls have run and assembled `biosample_exports`, but before the result is
posted to BioSamples, call `collect_ena_required_fields` to gather the values
each sample needs, then write them back into each sample's characteristics
under the INSDC-standard keys.

Two-pass logic:
  Pass 1 - direct hit. If a sample carries `specimen collection date` and
    `geographic location` in its own characteristics, use them.
  Pass 2 - chain walk. If a sample is missing them, follow `derived from`
    upward: reuse a sibling's resolved values, fetch from the BioSamples
    public API for SAM-prefixed accessions, or recurse to a more distant
    ancestor.
"""

import requests


def collect_ena_required_fields(biosample_exports):
    """
    Walk every sample across all sample types and collect the values for the
    two INSDC-mandatory fields.

    :param biosample_exports: dict of {sample_type: [{'sample_name': str,
        'biosample_format': {'characteristics': dict, 'relationships': list}}, ...]}
        as built by ExperimentSubmitter.export_valid_samples_to_biosample.
    :return: tuple (collection_date, geographic_location), each a dict
        {sample_name: value} ready to be written back into each sample's
        characteristics under the INSDC-standard keys.
    """
    collection_date = {}
    geographic_location = {}
    missing_ids = {}

    # Pass 1: walk every sample. Either populate directly, or record the
    # parent we need to resolve for it later.
    for sample_type, sample_list in biosample_exports.items():
        for sample in sample_list:
            sample_name = sample['sample_name']
            biosample_format = sample.get('biosample_format', {}) or {}
            characteristics = biosample_format.get('characteristics', {}) or {}

            has_specimen_date = 'specimen collection date' in characteristics
            has_geo_location = 'geographic location' in characteristics

            if has_specimen_date and has_geo_location:
                # Direct hit: pull the text values out of the BioSamples-format shape.
                collection_date[sample_name] = (
                    characteristics['specimen collection date'][0]['text']
                )
                geographic_location[sample_name] = (
                    characteristics['geographic location'][0]['text']
                )
                continue

            # Gap. See if there's a derived_from we can chase in pass 2.
            relationships = biosample_format.get('relationships', []) or []
            parent_id = next(
                (r['target'] for r in relationships if r.get('type') == 'derived from'),
                None,
            )
            if parent_id:
                missing_ids[sample_name] = parent_id

    # Pass 2: resolve every gap. The resolved values get keyed under the
    # CHILD's sample_name, not the parent's, because that's whose
    # characteristics will get the INSDC keys written back.
    for sample_name, parent_id in missing_ids.items():
        result = _resolve_from_parent(
            parent_id, collection_date, geographic_location, missing_ids
        )
        if result is not None:
            collection_date[sample_name], geographic_location[sample_name] = result

    return collection_date, geographic_location


def _resolve_from_parent(parent_id, collection_date, geographic_location, missing_ids):
    """
    Resolve the (collection_date, geographic_location) pair for a sample by
    walking back through its derived_from parent.

    Three cases:
      1. Parent is a sibling sample we've already resolved -> reuse its values.
      2. Parent looks like a BioSamples accession -> fetch from the public API.
      3. Otherwise (parent is another local sample we haven't resolved yet) ->
         recurse on missing_ids[parent_id] to walk further up the chain.

    :param parent_id: the derived_from target to resolve (BioSamples accession
        or local sample name)
    :param collection_date: dict {sample_name: collection_date_value} populated so far
    :param geographic_location: dict {sample_name: geographic_location_value} populated so far
    :param missing_ids: dict {sample_name: parent_id} of samples still awaiting resolution
    :return: tuple (collection_date_value, geographic_location_value), or None if
        the BioSamples API response can't be JSON-decoded (Django parity)
    """
    # Case 1: already resolved as a sibling
    if parent_id in collection_date and parent_id in geographic_location:
        return collection_date[parent_id], geographic_location[parent_id]

    # Case 2: looks like a BioSamples accession -> fetch from public API
    if 'SAM' in parent_id and '_' not in parent_id:
        try:
            results = requests.get(
                f"https://www.ebi.ac.uk/biosamples/samples/{parent_id}"
            ).json()
            if ('collection date' in results['characteristics']
                    and 'geographic location (country and/or sea)' in results['characteristics']):
                return (
                    results['characteristics']['collection date'][0]['text'],
                    results['characteristics']['geographic location (country and/or sea)'][0]['text'],
                )
            return 'not collected', 'not collected'
        except ValueError:
            # Django parity: silent swallow on JSON-decode failure.
            # Function returns None implicitly; caller writes None into the
            # dicts, and the eventual write-back skips the sample because the
            # `if name in collection_date and name in geographic_location`
            # guard fails. Latent bug carried over deliberately.
            pass
        return None

    # Case 3: parent is another local sample, still unresolved -> recurse
    return _resolve_from_parent(
        missing_ids[parent_id], collection_date, geographic_location, missing_ids
    )
