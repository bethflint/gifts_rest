"""
.. See the NOTICE file distributed with this work for additional information
   regarding copyright ownership.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

from __future__ import print_function

from rest_framework import serializers
from django.http import Http404

from restui.lib.external import ensembl_sequence
from restui.models.mappings import Mapping
from restui.models.mappings import MappingView
from restui.models.mappings import ReleaseMappingHistory
from restui.models.mappings import MappingHistory
from restui.models.mappings import ReleaseStats
from restui.models.ensembl import EnsemblSpeciesHistory
from restui.serializers.ensembl import SpeciesHistorySerializer
from restui.serializers.annotations import StatusHistorySerializer


class TaxonomySerializer(serializers.Serializer):
    """
    For nested serialization of taxonomy in call to mapping/<id> endpoint.
    """

    species = serializers.CharField()
    ensemblTaxId = serializers.IntegerField()
    uniprotTaxId = serializers.IntegerField()


class UniprotEntryMappingSerializer(serializers.Serializer):
    uniprot_id = serializers.IntegerField()
    uniprotAccession = serializers.CharField()
    entryType = serializers.CharField()
    sequenceVersion = serializers.IntegerField()
    upi = serializers.CharField()
    md5 = serializers.CharField()
    isCanonical = serializers.NullBooleanField()
    alias = serializers.CharField()
    ensemblDerived = serializers.NullBooleanField()
    gene_symbol = serializers.CharField()
    gene_accession = serializers.CharField()
    length = serializers.IntegerField()
    protein_existence_id = serializers.IntegerField()


class EnsemblTranscriptMappingSerializer(serializers.Serializer):
    transcript_id = serializers.IntegerField()
    enstId = serializers.CharField()
    enstVersion = serializers.IntegerField()
    upi = serializers.CharField()
    biotype = serializers.CharField()
    deleted = serializers.NullBooleanField()
    chromosome = serializers.CharField()
    regionAccession = serializers.CharField()
    seqRegionStart = serializers.IntegerField()
    seqRegionEnd = serializers.IntegerField()
    seqRegionStrand = serializers.IntegerField()
    ensgId = serializers.CharField()
    ensgName = serializers.CharField()
    sequence = serializers.CharField(required=False)
    ensgSymbol = serializers.CharField()
    ensgAccession = serializers.CharField()
    ensgRegionAccession = serializers.CharField()
    enspId = serializers.CharField()
    enspLen = serializers.IntegerField()
    source = serializers.CharField()
    select = serializers.NullBooleanField()


class EnsemblUniprotMappingSerializer(serializers.Serializer):
    """
    For nested serialization of Ensembl-Uniprot mapping in call to mapping/<id> endpoint.
    """

    # mapping_view id to get unmapped entry details
    id = serializers.IntegerField(required=False)
    mappingId = serializers.IntegerField()
    groupingId = serializers.IntegerField(required=False)
    timeMapped = serializers.DateTimeField()
    uniprotRelease = serializers.CharField()
    ensemblRelease = serializers.CharField()
    uniprotEntry = UniprotEntryMappingSerializer()
    ensemblTranscript = EnsemblTranscriptMappingSerializer()
    alignment_difference = serializers.IntegerField()
    status = serializers.CharField()
    status_history = StatusHistorySerializer(many=True)


class EnsemblUniprotRelatedUnmappedSerializer(serializers.Serializer):
    """
    Nested serialization of Ensembl-Uniprot unmapped entries related to a mapping
    """
    ensembl = EnsemblTranscriptMappingSerializer(many=True)
    uniprot = UniprotEntryMappingSerializer(many=True)


class RelatedEntriesSerializer(serializers.Serializer):
    """
    For nested serialization of mapped/unmapped mapping releated entries
    """

    mapped = EnsemblUniprotMappingSerializer(many=True)
    unmapped = EnsemblUniprotRelatedUnmappedSerializer()


class MappingSerializer(serializers.Serializer):
    """
    Serialize data in call to mapping/:id endpoint.

    JSON specs derived from:
    https://github.com/ebi-uniprot/gifts-mock/blob/master/data/mapping.json
    """

    taxonomy = TaxonomySerializer()
    mapping = EnsemblUniprotMappingSerializer()
    relatedEntries = RelatedEntriesSerializer()
    emailRecipientsList = serializers.DictField(child=serializers.CharField())


class MappingHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for MappingHistory instances
    """

    class Meta:
        model = MappingHistory
        fields = '__all__'


class ReleaseMappingHistorySerializer(serializers.ModelSerializer):
    """
    Serializers for ReleaseMappingHistory instances, includes nested ensembl
    species history
    """
    # mapping_history = MappingHistorySerializer(many=True)
    ensembl_species_history = SpeciesHistorySerializer()

    class Meta:
        model = ReleaseMappingHistory
        fields = '__all__'


class MappingByHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for mappings returned by the mappings/release_history/<id> endpoint.
    """

    mapping_history = MappingHistorySerializer(many=True)

    class Meta:
        model = Mapping
        fields = '__all__'


class MappingsSerializer(serializers.Serializer):
    """
    Serialize data in call to mappings/ endpoint
    """

    taxonomy = TaxonomySerializer()
    entryMappings = EnsemblUniprotMappingSerializer(many=True)

    @classmethod
    def build_mapping(cls, mapping, fetch_sequence=False, authenticated=False):
        mapping_history = mapping.mapping_history.select_related(
            'release_mapping_history'
        ).select_related(
            'release_mapping_history__ensembl_species_history'
        ).latest(
            'mapping_history_id'
        )

        release_mapping_history = mapping_history.release_mapping_history

        ensembl_history = mapping_history.release_mapping_history.ensembl_species_history

        status = mapping.status.id

        sequence = None
        if fetch_sequence:
            try:
                sequence = ensembl_sequence(
                    mapping.transcript.enst_id,
                    ensembl_history.ensembl_release
                )
            except Exception as e:
                print(e)
                sequence = None

        mapping_obj = {
            'mappingId': mapping.mapping_id,
            'timeMapped': release_mapping_history.time_mapped,
            'ensemblRelease': ensembl_history.ensembl_release,
            'uniprotRelease': release_mapping_history.uniprot_release,
            'uniprotEntry': {
                'uniprot_id': mapping.uniprot.uniprot_id,
                'uniprotAccession': mapping.uniprot.uniprot_acc,
                'entryType': Mapping.entry_type(mapping_history.entry_type_id),
                'sequenceVersion': mapping.uniprot.sequence_version,
                'upi': mapping.uniprot.upi,
                'md5': mapping.uniprot.md5,
                'isCanonical': not mapping.uniprot.canonical_uniprot_id,
                'alias': mapping.uniprot.alias,
                'ensemblDerived': mapping.uniprot.ensembl_derived,
                'gene_symbol': mapping.uniprot.gene_symbol,
                'gene_accession': mapping.uniprot.chromosome_line,
                'length': mapping.uniprot.length,
                'protein_existence_id': mapping.uniprot.protein_existence_id
            },
            'ensemblTranscript': {
                'transcript_id': mapping.transcript.transcript_id,
                'enstId': mapping.transcript.enst_id,
                'enstVersion': mapping.transcript.enst_version,
                'upi': mapping.transcript.uniparc_accession,
                'biotype': mapping.transcript.biotype,
                'deleted': mapping.transcript.deleted,
                'chromosome': mapping.transcript.gene.chromosome,
                'regionAccession': mapping.transcript.gene.region_accession,
                'seqRegionStart': mapping.transcript.seq_region_start,
                'seqRegionEnd': mapping.transcript.seq_region_end,
                'seqRegionStrand': mapping.transcript.gene.seq_region_strand,
                'ensgId': mapping.transcript.gene.ensg_id,
                'ensgName': mapping.transcript.gene.gene_name,
                'ensgSymbol': mapping.transcript.gene.gene_symbol,
                'ensgAccession': mapping.transcript.gene.gene_accession,
                'ensgRegionAccession': mapping.transcript.gene.region_accession,
                'sequence': sequence,
                'enspId': mapping.transcript.ensp_id,
                'enspLen': mapping.transcript.ensp_len,
                'source': mapping.transcript.source,
                'select': mapping.transcript.select
            },
            'alignment_difference': mapping.alignment_difference,
            'status': Mapping.status_type(status),
            'status_history': mapping.statuses(usernames=authenticated)
        }

        return mapping_obj

    @classmethod
    def build_mapping_group(cls, mappings_group, fetch_sequence=False):
        mapping_set = dict()
        try:
            mapping_set['taxonomy'] = cls.build_taxonomy_data(mappings_group[0])
        except Exception as e:
            # log
            print(e)
            err_str = "Couldn't create taxonomy element for mapping object {}"
            raise Http404(
                err_str.format(mappings_group[0].mapping_id)
            )

        mapping_set['entryMappings'] = []

        for mapping in mappings_group:
            mapping_set['entryMappings'].append(
                cls.build_mapping(
                    mapping,
                    fetch_sequence=fetch_sequence
                )
            )

        return mapping_set

    @classmethod
    def build_taxonomy_data(cls, mapping):
        """
        Find the ensembl tax id via one ensembl species history associated to
        transcript associated to the given mapping.

        Relationship between transcript and history is many to many but we just
        fetch one history as the tax id remains the same across all of them
        """
        try:
            ensembl_history = mapping.mapping_history.select_related(
                'release_mapping_history'
            ).select_related(
                'release_mapping_history__ensembl_species_history'
            ).latest(
                'mapping_history_id'
            ).release_mapping_history.ensembl_species_history
            # ensembl_history = mapping.transcript.history.latest('ensembl_release')
            uniprot_tax_id = mapping.uniprot.uniprot_tax_id
        except Exception as e:
            # log
            print(e)
            err_str = "Couldn't find an ensembl species history associated to mapping {}"
            raise Http404(
                err_str.format(mapping.mapping_id)
            )

        try:
            return {
                'species': ensembl_history.species,
                'ensemblTaxId': ensembl_history.ensembl_tax_id,
                'uniprotTaxId': uniprot_tax_id
            }
        except:
            raise Http404((
                "Couldn't find uniprot tax id as I couldn't find a uniprot "
                "entry associated to the mapping"
            ))


class MappingViewSerializer(serializers.ModelSerializer):
    """
    Serializer for MappingView instances
    """

    class Meta:
        model = MappingView
        fields = '__all__'


class MappingViewsSerializer(serializers.Serializer):
    """
    Serialize data in call to mappings/ endpoint
    """

    taxonomy = TaxonomySerializer()
    entryMappings = EnsemblUniprotMappingSerializer(many=True)

    @classmethod
    def build_mapping(cls, mapping_view, fetch_sequence=False, authenticated=False):
        status = mapping_view.status

        sequence = None
        if fetch_sequence:
            try:
                sequence = ensembl_sequence(
                    mapping_view.enst_id,
                    mapping_view.ensembl_release
                )
            except Exception as e:
                print(e)
                sequence = None

        mapping_obj = {
            'id': mapping_view.id,
            'mappingId': mapping_view.mapping_id,
            'groupingId': mapping_view.grouping_id,
            'timeMapped': mapping_view.time_mapped,
            'ensemblRelease': mapping_view.ensembl_release,
            'uniprotRelease': mapping_view.uniprot_release,
            'uniprotEntry': {
                'uniprot_id': mapping_view.uniprot_id,
                'uniprotAccession': mapping_view.uniprot_acc,
                'entryType': MappingView.entry_description(mapping_view.entry_type),
                'sequenceVersion': mapping_view.sequence_version,
                'upi': mapping_view.upi,
                'md5': mapping_view.md5,
                'isCanonical': not mapping_view.canonical_uniprot_id,
                'alias': mapping_view.alias,
                'ensemblDerived': mapping_view.ensembl_derived,
                'gene_symbol': mapping_view.gene_symbol_up,
                'gene_accession': mapping_view.chromosome_line,
                'length': mapping_view.length,
                'protein_existence_id': mapping_view.protein_existence_id
            },
            'ensemblTranscript': {
                'transcript_id': mapping_view.transcript_id,
                'enstId': mapping_view.enst_id,
                'enstVersion': mapping_view.enst_version,
                'upi': mapping_view.uniparc_accession,
                'biotype': mapping_view.biotype,
                'deleted': mapping_view.deleted,
                'chromosome': mapping_view.chromosome,
                'regionAccession': mapping_view.region_accession,
                'seqRegionStart': mapping_view.seq_region_start,
                'seqRegionEnd': mapping_view.seq_region_end,
                'seqRegionStrand': mapping_view.seq_region_strand,
                'ensgId': mapping_view.ensg_id,
                'ensgName': mapping_view.gene_name,
                'ensgSymbol': mapping_view.gene_symbol_eg,
                'ensgAccession': mapping_view.gene_accession,
                'ensgRegionAccession': mapping_view.region_accession,
                'sequence': sequence,
                'enspId': mapping_view.ensp_id,
                'enspLen': mapping_view.ensp_len,
                'source': mapping_view.source,
                'select': mapping_view.select
            },
            'alignment_difference': mapping_view.alignment_difference,
            'status': MappingView.status_description(status),
            'status_history': mapping_view.statuses(usernames=authenticated)
        }

        return mapping_obj

    @classmethod
    def build_mapping_group(cls, group, fetch_sequence=False):
        mapping_set = {
            'taxonomy': cls.build_taxonomy_data(group),
            'entryMappings': []
        }

        for mapping_view in group:
            mapping_set['entryMappings'].append(
                cls.build_mapping(
                    mapping_view,
                    fetch_sequence=fetch_sequence
                )
            )

        return mapping_set

    @classmethod
    def build_taxonomy_data(cls, group):
        """
        Find taxonomy information, i.e. ensembl/uniprot tax id/species for the
        group

        if the group contains mapped and potentially unmapped data
        return information from the first mapping with could find
        taxonomy data from
        """
        for mapping_view in group:
            try:
                mapping = Mapping.objects.get(pk=mapping_view.mapping_id)
            except Mapping.DoesNotExist:
                continue

            ensembl_history = mapping.mapping_history.select_related(
                'release_mapping_history'
            ).select_related(
                'release_mapping_history__ensembl_species_history'
            ).latest(
                'mapping_history_id'
            ).release_mapping_history.ensembl_species_history

            return {
                'species': ensembl_history.species,
                'ensemblTaxId': ensembl_history.ensembl_tax_id,
                'uniprotTaxId': mapping_view.uniprot_tax_id
            }

        # The group just contains unmapped data, but the entries can belong
        # to multiple species. Return information only if the group refers to
        # the same tax id.
        tax_ids = []
        for mapping_view in group:
            tax_ids.append(mapping_view.uniprot_tax_id)

        if len(tax_ids) == 1:
            species_history = EnsemblSpeciesHistory.objects.filter(
                ensembl_tax_id=tax_ids[0]
            ).latest(
                'time_loaded'
            )

            return {
                'species': species_history.species,
                'ensemblTaxId': species_history.ensembl_tax_id,
                'uniprotTaxId': group[0].uniprot_tax_id
            }

        return {
            'species': None,
            'ensemblTaxId': None,
            'uniprotTaxId': None
        }


class CommentLabelSerializer(serializers.Serializer):
    """
    For nested serialization of user comment for a mapping in call to
    mapping/<id>/comments/ endpoint.
    """

    commentId = serializers.IntegerField()
    text = serializers.CharField()
    timeAdded = serializers.DateTimeField()
    user = serializers.CharField()
    editable = serializers.BooleanField()


class MappingCommentsSerializer(serializers.Serializer):
    """
    Serialize data in call to comments/<mapping_id> endpoint.

    JSON specs derived from:
        https://github.com/ebi-uniprot/gifts-mock/blob/master/data/comments.json
    """

    mappingId = serializers.IntegerField()
    comments = CommentLabelSerializer(many=True)


class MappingPairwiseAlignmentSerializer(serializers.Serializer):
    """
    For a nested pairwise alignment object
    """
    uniprot_alignment = serializers.CharField()
    ensembl_alignment = serializers.CharField()
    match_str = serializers.CharField()
    alignment_id = serializers.IntegerField()
    alignment_type = serializers.CharField()
    ensembl_release = serializers.IntegerField()
    ensembl_id = serializers.CharField()
    uniprot_id = serializers.CharField()


class MappingAlignmentsSerializer(serializers.Serializer):
    """
    Serializer for pairwise alignment sets
    """
    mapping_id = serializers.IntegerField()
    alignments = MappingPairwiseAlignmentSerializer(many=True)


class UniprotMappedCountSerializer(serializers.Serializer):
    """
    Serializer for counts related to mapped/unmapped Uniprot entries
    """

    mapped = serializers.IntegerField()
    not_mapped_sp = serializers.IntegerField()


class EnsemblMappedCountSerializer(serializers.Serializer):
    """
    Serializer for counts related to mapped/unmapped gene/transcript entries
    """

    gene_mapped = serializers.IntegerField()
    gene_not_mapped_sp = serializers.IntegerField()
    transcript_mapped = serializers.IntegerField()


class MappingCountSerializer(serializers.Serializer):
    """
    Serializer for general and specific mapping counts
    """

    total = serializers.IntegerField()
    uniprot = UniprotMappedCountSerializer()
    ensembl = EnsemblMappedCountSerializer()


class StatusCountSerializer(serializers.Serializer):
    """
    Serializer for an individual status' count
    """
    status = serializers.CharField()
    count = serializers.IntegerField()


class LabelCountSerializer(serializers.Serializer):
    """
    Serializer for an individual label's count
    """
    label = serializers.CharField()
    count = serializers.IntegerField()


class ReleaseStatsSerializer(serializers.ModelSerializer):
    """
    Serializer for ReleaseStats instances
    """

    class Meta:
        model = ReleaseStats
        fields = '__all__'


class ReleasePerSpeciesSerializer(serializers.Serializer):
    """
    Serializer for ensembl/uniprot release numbers /mappings/release/<taxid>/
    endpoint
    """

    ensembl = serializers.IntegerField()
    uniprot = serializers.CharField()
