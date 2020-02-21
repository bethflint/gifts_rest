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

import os
import json
import mock

from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from django.http import Http404

from restui.models.ensembl import EnsemblGene
from restui.models.ensembl import EnsemblTranscript
from restui.models.ensembl import EnsemblSpeciesHistory
from restui.models.mappings import Mapping
from restui.models.uniprot import UniprotEntry

from restui.exceptions import FalloverROException
from restui.lib import alignments
from restui.lib import external
from restui.views import mappings
from restui.views import unmapped
from restui.views import version

FIXTURES = [
    'ensembl_gene', 'ensembl_transcript', 'uniprot_entry',
    'cv_ue_status', 'mapping', 'ensembl_species_history',
    'release_mapping_history', 'alignment_run', 'alignment',
    'ensp_u_cigar', 'transcript_history', 'cv_entry_type',
    'mapping_view', 'mapping_history', 'release_stats', 'cv_ue_label',
    'aapuser', 'ue_mapping_label', 'ue_unmapped_entry_label',
    'uniprot_entry_history'
]


class EnsemblTest(APITestCase):
    """
    Test that data is present in the test db
    """

    fixtures = FIXTURES

    def test_ensemblgene_request(self):
        gene = EnsemblGene.objects.filter(pk=2).values()
        self.assertEqual(gene[0]['gene_name'], 'RAD1')

    def test_ensembltranscript_request(self):
        transcript = EnsemblTranscript.objects.filter(pk=2).values()
        self.assertEqual(transcript[0]['gene_id'], 1)

    def test_uniprot_entry_request(self):
        uniprot_entry = UniprotEntry.objects.filter(pk=1)
        self.assertEqual(
            str(uniprot_entry[0]),
            "{0} - {1}".format(
                uniprot_entry[0].uniprot_id,
                uniprot_entry[0].uniprot_acc
            )
        )

    def test_mapping_tables(self):
        maps = Mapping.objects.all()
        mapped_sets = maps.grouped_counts()
        self.assertEqual(mapped_sets[0]['total'], 2)

    def test_ensembl_species_history_request(self):
        mapping = mappings.get_mapping(1)
        ensembl_species_history = EnsemblSpeciesHistory.objects.filter(
            transcripthistory__transcript=mapping.transcript
        ).latest('time_loaded')
        self.assertEqual(ensembl_species_history.assembly_accession, 'GRCh37')

        mapping = mappings.get_mapping(2)
        ensembl_species_history = EnsemblSpeciesHistory.objects.filter(
            transcripthistory__transcript=mapping.transcript
        ).latest('time_loaded')
        self.assertEqual(ensembl_species_history.assembly_accession, 'GRCh38')

        mapping = mappings.get_mapping(3)
        ensembl_species_history = EnsemblSpeciesHistory.objects.filter(
            transcripthistory__transcript=mapping.transcript
        ).latest('time_loaded')
        self.assertEqual(ensembl_species_history.assembly_accession, 'GRCh38')

        mapping = mappings.get_mapping(4)
        ensembl_species_history = EnsemblSpeciesHistory.objects.filter(
            transcripthistory__transcript=mapping.transcript
        ).latest('time_loaded')
        self.assertEqual(ensembl_species_history.assembly_accession, 'GRCh38')

        mock_mapping = mock.Mock(spec=Mapping)
        mock_mapping.transcript = 2

        ensembl_species_history = EnsemblSpeciesHistory.objects.filter(
            transcripthistory__transcript=mock_mapping.transcript
        ).latest('time_loaded')
        self.assertEqual(ensembl_species_history.assembly_accession, 'GRCh38')


class EnsemblAlignment(APITestCase):
    """
    endpoints of /alignments
    """

    fixtures = FIXTURES

    def test_alignment_alignments_run_request(self):
        client = APIClient()
        response = client.get('/alignments/alignment/alignment_run/1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['alignment_run'], 1)

    def test_alignment_request(self):
        client = APIClient()
        response = client.get('/alignments/alignment/1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['alignment_id'], 1)

    def test_alignments_assembly_request(self):
        client = APIClient()
        response = client.get('/alignments/alignment/latest/assembly/GRCh38/?type=identity')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['alignment_id'], 2)

    def test_alignment_run_request(self):
        client = APIClient()
        response = client.get('/alignments/alignment_run/1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['alignment_run_id'], 1)

    def test_alignment_run_post(self):
        client = APIClient()
        response = client.post(
            '/alignments/alignment_run/',
            data={
                'userstamp': 'test_userstamp',
                'time_run': '2019-05-01 00:00:00',
                'score1_type': 'perfect_match',
                'report_type': 'sp mapping value',
                'pipeline_name': 'test_loading',
                'pipeline_comment': 'test',
                'ensembl_release': 0,
                'uniprot_file_swissprot': '/test/location/sp.txt',
                'uniprot_file_isoform': '/test/location/iso.txt',
                'uniprot_dir_trembl': '/test/location/trembl',
                'logfile_dir': '/test/location/log.txt',
                'pipeline_script': 'testing_testing.sh',
                'score2_type': 'coverage',
                'release_mapping_history': 1
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['alignment_run_id'], 3)

        client = APIClient()
        response = client.post(
            '/alignments/alignment/',
            data={
                'uniprot_id': 2,
                'score1': 1,
                'report': 'Alignment',
                'is_current': True,
                'score2': 1,
                'alignment_run': 3,
                'transcript': 2,
                'mapping': 2
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['alignment_id'], 4)


class EnsemblEnsembl(APITestCase):
    """
    Endpoints of /ensembl
    """

    fixtures = FIXTURES

    def test_cigar_post(self):
        client = APIClient()
        response_1 = client.post(
            '/alignments/alignment_run/',
            data={
                'userstamp': 'test_userstamp',
                'time_run': '2019-05-01 00:00:00',
                'score1_type': 'perfect_match',
                'report_type': 'sp mapping value',
                'pipeline_name': 'test_loading',
                'pipeline_comment': 'test',
                'ensembl_release': 0,
                'uniprot_file_swissprot': '/test/location/sp.txt',
                'uniprot_file_isoform': '/test/location/iso.txt',
                'uniprot_dir_trembl': '/test/location/trembl',
                'logfile_dir': '/test/location/log.txt',
                'pipeline_script': 'testing_testing.sh',
                'score2_type': 'coverage',
                'release_mapping_history': 1
            }
        )

        response_2 = client.post(
            '/alignments/alignment/',
            data={
                'uniprot_id': 2,
                'score1': 1,
                'report': 'Alignment',
                'is_current': True,
                'score2': 1,
                'alignment_run': response_1.data['alignment_run_id'],
                'transcript': 2,
                'mapping': 2
            }
        )

        response_3 = client.post(
            '/ensembl/cigar/',
            data={
                'alignment': response_2.data['alignment_id'],
                'cigarplus': 'M',
                'mdz': 'abcd'
            }
        )
        self.assertEqual(response_3.status_code, 201)
        self.assertEqual(
            response_3.data['alignment'],
            response_2.data['alignment_id']
        )

    def test_cigar_align_run_request(self):
        client = APIClient()
        response = client.get(
            '/ensembl/cigar/align_run/2/uniprot/P51587/1/transcript/ENST00000380152.7/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['alignment'], 3)

    def test_cigar_alignment_get_request(self):
        client = APIClient()
        response = client.get('/ensembl/cigar/alignment/1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['alignment'], 1)

    def test_ensembl_feature_request(self):
        resource_path = os.path.join(
            os.path.dirname(__file__),
            'fixtures/demo_bulk_load.json'
        )
        with open(resource_path, 'r') as json_file:
            json_block = json.loads(json_file.read())

        client = APIClient()
        response = client.post(
            '/ensembl/load/homo_sapiens/GRCh38/9606/97/',
            json_block,
            format='json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('task_id', response.data)

    def test_latest_assembly_request(self):
        client = APIClient()
        response = client.get('/ensembl/release/latest/assembly/GRCh38/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['release'], 95)

    def test_spp_history_post(self):
        client = APIClient()
        response = client.post(
            '/ensembl/species_history/1/alignment_status/ALIGNMENT_TEST/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['alignment_status'], 'ALIGNMENT_TEST')

    def test_spp_history_request(self):
        client = APIClient()
        response = client.get('/ensembl/species_history/2/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['assembly_accession'], 'GRCh38')
        self.assertEqual(response.data['alignment_status'], 'ALIGNMENT_COMPLETED')

    def test_transcript_request(self):
        client = APIClient()
        response = client.get('/ensembl/transcript/2/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['enst_id'], 'ENST00000380152.7')


class EnsemblMapping(APITestCase):
    """
    Endpoints of /mapping
    """

    fixtures = FIXTURES

    def test_mapping_functions(self):
        with self.assertRaises(Http404):
            mapping = mappings.get_mapping(99)

        mapping = mappings.get_mapping(3)
        self.assertEqual(mapping.transcript.gene.gene_name, 'BRCA2')
        self.assertEqual(mapping.uniprot.uniprot_acc, 'P51587')

        with self.assertRaises(Http404):
            mock_mapping = mock.Mock(spec=Mapping)
            mock_mapping.transcript = 99
            tax = mappings.build_taxonomy_data(
                mock_mapping
            )

        tax = mappings.build_taxonomy_data(mapping)
        self.assertEqual(tax['ensemblTaxId'], 9606)

        related_mappings = mappings.build_related_mappings_data(mapping)
        self.assertEqual(related_mappings[0]['mappingId'], 4)
        self.assertEqual(
            related_mappings[0]['ensemblTranscript']['ensgId'],
            'ENSG00000139618'
        )
        self.assertEqual(
            related_mappings[0]['ensemblTranscript']['ensgName'],
            'BRCA2'
        )
        self.assertEqual(
            related_mappings[0]['ensemblTranscript']['enstId'],
            'ENST00000380152.7'
        )
        self.assertEqual(
            related_mappings[0]['uniprotEntry']['uniprotAccession'],
            'O60671'
        )

        unrelated_mappings = mappings.build_related_unmapped_entries_data(mapping)
        self.assertEqual(unrelated_mappings['ensembl'], [])
        self.assertEqual(len(unrelated_mappings['uniprot']), 3)

    def test_mapping_request(self):
        client = APIClient()
        response = client.get('/mapping/1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mapping']['mappingId'], 1)

    def test_mapping_labels_request(self):
        client = APIClient()

        mapping = mappings.get_mapping(1)
        mapped_label = mapping.labels.values_list('label', flat=True)[0]

        # View labels
        response = client.get('/mapping/1/labels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['labels'][mapped_label - 1]['status'], True)

        # Add label - mappings.MappingLabelView
        response = client.post('/mapping/1/labels/4/')
        self.assertEqual(response.status_code, 204)

        response = client.get('/mapping/1/labels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['labels'][mapped_label - 1]['status'], True)
        self.assertEqual(response.data['labels'][3]['status'], True)

        # Delete label - mappings.MappingLabelView
        response = client.delete('/mapping/1/labels/4/')
        self.assertEqual(response.status_code, 204)

        response = client.get('/mapping/1/labels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['labels'][3]['status'], False)

        # Try to delete previsouly deleted label - mappings.MappingLabelView
        response = client.delete('/mapping/1/labels/4/')
        self.assertEqual(response.status_code, 404)

    def test_mapping_pairwise_request(self):
        client = APIClient()
        response = client.get('/mapping/1/pairwise/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['mapping_id'], 1)

    def test_mapping_alignment_diff_request(self):
        client = APIClient()
        response = client.post('/mapping/1/alignment_difference/5/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['alignment_difference'], 5)

    def test_mapping_comment_requests(self):
        client = APIClient()
        # client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        # client.credentials(HTTP_AUTHORIZATION='Token testtesttest123')

        # client.login(username='testtesttest123', password='check')

        # client.session.auth = HTTPBasicAuth('testtesttest123', 'check')

        # print("\nUSERS:", AAPUser.objects.all().values())
        # user = AAPUser.objects.filter(elixir_id='testtesttest123')
        # print("\nUSER:", user)
        # client.force_authenticate(user=user)
        # print("\nFORCE AUTH")

        # View comment - mappings.MappingCommentsView
        response = client.get('/mapping/1/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comments'], [])

        # Add a comment - mappings.MappingCommentsView
        response = client.post(
            '/mapping/1/comments/',
            data={
                'text': 'This is a test comment',
                'email_recipient_ids': [1]
            },
            format='json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id'], 1)

        # View a comment
        response = client.get('/mapping/1/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comments'][0]['text'], 'This is a test comment')
        self.assertEqual(response.data['comments'][0]['user'], 'Zapp Brannigan')

        # Edit a comment - mappings.EditDeleteCommentView
        response = client.put(
            '/mapping/1/comments/1/',
            data={
                'text': 'This is a changed comment'
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['commentId'], 1)

        # View a comment
        response = client.get('/mapping/1/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['comments'][0]['text'],
            'This is a changed comment'
        )
        self.assertEqual(
            response.data['comments'][0]['user'],
            'Zapp Brannigan'
        )

        response = client.put(
            '/mapping/1/comments/1/',
            data={}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Text not specified')

        response = client.put(
            '/mapping/1/comments/99/',
            data={
                'text': 'Editing a non-existent comment'
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Invalid comment ID: 99')

        # Delete a comment - mappings.EditDeleteCommentView
        response = client.delete('/mapping/1/comments/1/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, None)

        response = client.delete('/mapping/1/comments/99/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Invalid comment ID: 99')

        # View comment - mappings.MappingCommentsView
        response = client.get('/mapping/1/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comments'], [])

        # Edit a deleted comment - mappings.EditDeleteCommentView
        response = client.put(
            '/mapping/1/comments/1/',
            data={
                'text': 'This is not possible'
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Cannot edit deleted comment')

    def test_mapping_status_request(self):
        client = APIClient()

        response = client.put(
            '/mapping/2/status/',
            data={}
        )
        self.assertEqual(response.status_code, 404)

        response = client.put(
            '/mapping/2/status/',
            data={
                'status': 999
            }
        )
        self.assertEqual(response.status_code, 404)

        response = client.put(
            '/mapping/2/status/',
            data={
                'status': 'TESTING2'
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['mapping'], 2)

        response = client.put(
            '/mapping/2/status/',
            data={
                'status': 'TESTING2'
            }
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, None)


class EnsemblMappings(APITestCase):
    """
    Endpoints of /mappings
    """

    fixtures = FIXTURES

    def test_mappings_request(self):
        client = APIClient()
        response = client.get('/mappings/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 3)

        # Search Terms - mappings.MappingViewsSearch
        response = client.get('/mappings/?searchTerm=ENSG00000139618')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        response = client.get('/mappings/?searchTerm=ENST00000380152.7')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        response = client.get('/mappings/?searchTerm=P51587')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        response = client.get('/mappings/?searchTerm=BRCA2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        # Facet Terms - Organism - mappings.MappingViewsSearch
        response = client.get('/mappings/?facets=organism:9606')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 3)

        # Facet Terms - Alignment - mappings.MappingViewsSearch
        response = client.get('/mappings/?facets=alignment:identical')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        response = client.get('/mappings/?facets=alignment:small')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)

        response = client.get('/mappings/?facets=alignment:large')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        # Facet Terms - Status - mappings.MappingViewsSearch
        response = client.get('/mappings/?facets=status:testing')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        response = client.get('/mappings/?facets=status:invalid')
        self.assertEqual(response.status_code, 404)

        # Facet Terms - Chromosomes - mappings.MappingViewsSearch
        response = client.get('/mappings/?facets=chromosomes:1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        # Facet Terms - Type - mappings.MappingViewsSearch
        response = client.get('/mappings/?facets=type:mapped')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        # Facet Terms - Patches - mappings.MappingViewsSearch
        response = client.get('/mappings/?facets=patches:exclude')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)

        response = client.get('/mappings/?facets=patches:only')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_mappings_release_request(self):
        client = APIClient()
        response = client.get('/mappings/release/9606/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['ensembl'], 95)
        self.assertEqual(response.data['uniprot'], '2019_05')

    def test_mappings_release_history_latest_request(self):
        client = APIClient()
        response = client.get('/mappings/release_history/latest/assembly/GRCh38/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'MAPPING_COMPLETED')

    def test_mappings_release_history_request(self):
        """
        This raises an UnorderedObjectListWarning
        """
        client = APIClient()
        response = client.get('/mappings/release_history/1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_mappings_stats_request(self):
        client = APIClient()
        response = client.get('/mappings/stats/9606/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(isinstance(response.data, dict), True)

    def test_mappings_status_request(self):
        client = APIClient()
        response = client.get('/mappings/statuses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], 1)
        self.assertEqual(response.data[0]['description'], 'TESTING')


class EnsemblService(APITestCase):
    """
    Endpoints of /service
    """

    fixtures = FIXTURES

    def test_service_ping(self):
        client = APIClient()
        response = client.get('/service/ping/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['ping'], 0)

    def test_service_status(self):
        client = APIClient()
        response = client.get('/service/status')
        self.assertEqual(response.status_code, 200)
        self.assertIn('ensembl_load_running', response.data)
        self.assertEqual(response.data['ensembl_load_running'], False)
        self.assertIn('uniprot_load_running', response.data)
        self.assertEqual(response.data['uniprot_load_running'], False)
        self.assertIn('gifts_mapping_running', response.data)
        self.assertEqual(response.data['gifts_mapping_running'], False)


class EnsemblUniProt(APITestCase):
    """
    Endpoints of /uniprot
    """

    fixtures = FIXTURES

    def test_uniprot_request(self):
        client = APIClient()
        response = client.get('/uniprot/entry/2/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['uniprot_acc'], 'O60671')


class EnsemblUnmapped(APITestCase):
    """
    Endpoints of /unmapped
    """

    fixtures = FIXTURES

    def test_get_uniprot_entry(self):
        uniprot_entry = unmapped.get_uniprot_entry(1)
        self.assertEqual(uniprot_entry.uniprot_acc, "P51587")

    def test_unmapped_request(self):
        client = APIClient()
        response = client.get('/unmapped/2/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['entry']['uniprot_acc'], "P54792")

    def test_unmapped_labels_request(self):
        uniprot_entry = unmapped.get_uniprot_entry(4)
        mapped_label = uniprot_entry.labels.values_list('label', flat=True)[0]

        client = APIClient()
        response = client.get('/unmapped/4/labels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['labels'][mapped_label - 1]['status'],
            True
        )

        # Add label - mappings.MappingLabelView
        response = client.post('/unmapped/4/labels/4/')
        self.assertEqual(response.status_code, 201)

        response = client.get('/unmapped/4/labels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['labels'][mapped_label - 1]['status'], True)
        self.assertEqual(response.data['labels'][3]['status'], True)

        # Delete label - mappings.MappingLabelView
        response = client.delete('/unmapped/4/labels/4/')
        self.assertEqual(response.status_code, 204)

        response = client.get('/unmapped/4/labels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['labels'][3]['status'], False)

        # Try to delete previsouly deleted label - mappings.MappingLabelView
        response = client.delete('/unmapped/4/labels/4/')
        self.assertEqual(response.status_code, 404)

    def test_unmapped_tax_source_ensembl_request(self):
        client = APIClient()
        response = client.get('/unmapped/9606/ensembl/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['results'][0]['transcripts'][0]['enstId'],
            'ENST00000544455.5'
        )

    def test_unmapped_tax_source_swissprot_request(self):
        client = APIClient()
        response = client.get('/unmapped/9606/swissprot/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['results'][0]['uniprotAccession'],
            'PUNM4P'
        )

    def test_unmapped_comment_requests(self):
        client = APIClient()
        # client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        # client.credentials(HTTP_AUTHORIZATION='Token testtesttest123')

        # client.login(username='testtesttest123', password='check')

        # client.session.auth = HTTPBasicAuth('testtesttest123', 'check')

        # print("\nUSERS:", AAPUser.objects.all().values())
        # user = AAPUser.objects.filter(elixir_id='testtesttest123')
        # print("\nUSER:", user)
        # client.force_authenticate(user=user)
        # print("\nFORCE AUTH")

        # View comment - unmapped.AddGetComments
        response = client.get('/unmapped/2/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comments'], [])

        # Add a comment - unmapped.AddGetComments
        response = client.post(
            '/unmapped/2/comments/',
            data={
                'text': 'This is a test comment'
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id'], 1)

        # View a comment - unmapped.AddGetComments
        response = client.get('/unmapped/2/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comments'][0]['text'], 'This is a test comment')
        self.assertEqual(response.data['comments'][0]['user'], 'Zapp Brannigan')

        # Edit a comment - unmapped.EditDeleteComment
        response = client.put(
            '/unmapped/2/comments/1/',
            data={
                'text': 'This is a changed comment'
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['commentId'], 1)

        # View a comment - unmapped.AddGetComments
        response = client.get('/unmapped/2/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['comments'][0]['text'],
            'This is a changed comment'
        )
        self.assertEqual(
            response.data['comments'][0]['user'],
            'Zapp Brannigan'
        )

        response = client.put(
            '/unmapped/2/comments/1/',
            data={}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Text not specified')

        response = client.put(
            '/unmapped/2/comments/99/',
            data={
                'text': 'Editing a non-existent comment'
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Invalid comment ID: 99')

        # Delete a comment - unmapped.EditDeleteComment
        response = client.delete('/unmapped/2/comments/1/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, None)

        response = client.delete('/unmapped/2/comments/99/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Invalid comment ID: 99')

        # View comment - mappings.MappingCommentsView
        response = client.get('/unmapped/2/comments/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comments'], [])

        # Edit a deleted comment - unmapped.EditDeleteComment
        response = client.put(
            '/unmapped/2/comments/1/',
            data={
                'text': 'This is not possible'
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'Cannot edit deleted comment')

    def test_unmapped_status_request(self):
        client = APIClient()

        response = client.put(
            '/unmapped/2/status/',
            data={}
        )
        self.assertEqual(response.status_code, 404)

        response = client.put(
            '/unmapped/2/status/',
            data={
                'status': 999
            }
        )
        self.assertEqual(response.status_code, 404)

        response = client.put(
            '/unmapped/2/status/',
            data={
                'status': 'TESTING2'
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['uniprot'], 3)

        response = client.put(
            '/unmapped/2/status/',
            data={
                'status': 'TESTING2'
            }
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, None)

        response = client.put(
            '/unmapped/2/status/',
            data={
                'status': 'TESTING'
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['uniprot'], 3)


class RestExceptions(APITestCase):
    """
    Tests to ensure that the custom exceptions can be raised
    """

    def test_falloverroeexception(self):
        """
        Exception to be raised when the service is in a read-only mode
        """
        with self.assertRaises(FalloverROException):
            raise FalloverROException


class LibAlignment(APITestCase):
    """
    Tests for the /lib/alignment functions
    """

    fixtures = [
        'ensembl_gene', 'ensembl_transcript', 'uniprot_entry',
        'cv_ue_status', 'mapping', 'ensembl_species_history',
        'release_mapping_history', 'alignment_run', 'alignment',
        'ensp_u_cigar', 'transcript_history', 'cv_entry_type',
        'mapping_history'
    ]

    def test_fetch_pairwise(self):
        mapping = Mapping.objects.prefetch_related(
            'alignments'
        ).select_related(
            'transcript'
        ).select_related(
            'uniprot'
        ).get(pk=3)

        pwaln = alignments.fetch_pairwise(mapping)

        self.assertEqual(
            pwaln['alignments'][0]['uniprot_alignment'][0:7],
            'MPIGSKE'
        )
        self.assertEqual(
            pwaln['alignments'][0]['ensembl_alignment'][0:7],
            'MPIGSKE'
        )

    def test_fetch_alignment(self):
        mapping = Mapping.objects.prefetch_related(
            'alignments'
        ).select_related(
            'transcript'
        ).select_related(
            'uniprot'
        ).get(pk=3)

        enst = mapping.transcript.enst_id
        uniprot_id = mapping.uniprot.uniprot_acc
        mapped_aln = mapping.alignments.all()

        aln = alignments._fetch_alignment(  # pylint: disable=protected-access
            mapped_aln[0], enst, uniprot_id
        )
        self.assertEqual(aln['uniprot_alignment'][0:7], 'MPIGSKE')

    def test_fetch_alignment_identity(self):
        client = APIClient()
        response = client.post(
            '/alignments/alignment_run/',
            data={
                'userstamp': 'test_userstamp',
                'time_run': '2019-05-01 00:00:00',
                'score1_type': 'identity',
                'report_type': 'sp mapping value',
                'pipeline_name': 'test_loading',
                'pipeline_comment': 'test',
                'ensembl_release': 0,
                'uniprot_file_swissprot': '/test/location/sp.txt',
                'uniprot_file_isoform': '/test/location/iso.txt',
                'uniprot_dir_trembl': '/test/location/trembl',
                'logfile_dir': '/test/location/log.txt',
                'pipeline_script': 'testing_testing.sh',
                'score2_type': 'coverage',
                'release_mapping_history': 1
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['alignment_run_id'], 3)

        client = APIClient()
        response = client.post(
            '/alignments/alignment/',
            data={
                'uniprot_id': 3,
                'score1': 1,
                'report': 'Alignment',
                'is_current': True,
                'score2': 1,
                'alignment_run': 3,
                'transcript': 2,
                'mapping': 2
            }
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['alignment_id'], 4)

    def test_calculate_difference(self):
        diff = alignments.calculate_difference('3M1I3M1D5M')
        self.assertEqual(diff, 2)


class LibExternal(APITestCase):
    """
    Tests for the /lib/external functions
    """

    def test_tark_transcript(self):
        tark_entry = external.tark_transcript('ENST00000382038', 95)
        self.assertEqual(tark_entry['stable_id'], 'ENST00000382038')

    def test_ensembl_current_release(self):
        e_release = external.ensembl_current_release()
        self.assertEqual(isinstance(e_release, int), True)

    def test_ensembl_sequence(self):
        seq = external.ensembl_sequence('ENST00000382038', 95)
        self.assertEqual(seq[0:7], 'GCTTGCC')

    def test_ensembl_protein(self):
        prot = external.ensembl_protein('ENST00000382038', 95)
        self.assertEqual(prot, 'ENSP00000371469')


class APIVersion(APITestCase):
    """
    Tests for endpoint version/
    """

    def test_api_version(self):
        client = APIClient()
        response = client.get('/version/')
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.data['version'],
                         r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
