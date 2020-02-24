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

from django.http import Http404

from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.schemas import ManualSchema

import coreapi
import coreschema

from restui.models.mappings import Alignment
from restui.models.mappings import AlignmentRun
from restui.serializers.alignments import AlignmentSerializer
from restui.serializers.alignments import AlignmentRunSerializer


class AlignmentRunCreate(generics.CreateAPIView):
    """
    Store an AlignmentRun
    """

    serializer_class = AlignmentRunSerializer


class AlignmentRunFetch(generics.RetrieveAPIView):
    """
    Retrieve an AlignmentRun
    """

    queryset = AlignmentRun.objects.all()
    serializer_class = AlignmentRunSerializer


class AlignmentCreate(generics.CreateAPIView):
    """
    Insert an Alignment
    """

    serializer_class = AlignmentSerializer


class AlignmentFetch(generics.RetrieveAPIView):
    """
    Retrieve an Alignment
    """

    queryset = Alignment.objects.all()
    serializer_class = AlignmentSerializer


class AlignmentByAlignmentRunFetch(generics.ListAPIView):
    """
    Retrieve all alignments for a given alignment run
    """

    serializer_class = AlignmentSerializer
    pagination_class = PageNumberPagination
    schema = ManualSchema(
        description="Retrieve all alignments for a given alignment run",
        fields=[
            coreapi.Field(
                name="id",
                required=True,
                location="path",
                schema=coreschema.Integer(),
                description="Alignmet run id"
            )
        ]
    )

    def get_queryset(self):
        try:
            alignment_run = AlignmentRun.objects.get(pk=self.kwargs["pk"])
        except (AlignmentRun.DoesNotExist, IndexError):
            raise Http404

        return Alignment.objects.filter(alignment_run=alignment_run).order_by('alignment_id')


#
# TODO
#
# We should probably filter to those whose mapping has been completed
# (i.e. MAPPING_COMPLETE in release_mapping_history)
#
class LatestAlignmentsFetch(generics.ListAPIView):
    """
    Retrieve either perfect or blast latest alignments for a given assembly
    """

    serializer_class = AlignmentSerializer
    pagination_class = PageNumberPagination
    schema = ManualSchema(
        description="Retrieve either perfect or blast latest alignments for a given assembly",
        fields=[
            coreapi.Field(
                name="assembly_accession",
                required=True,
                location="path",
                schema=coreschema.String(),
                description="Assembly accession"
            ),
            coreapi.Field(
                name="type",
                location="query",
                schema=coreschema.String(),
                description=(
                    "Type of the alignments to retrieve, either 'perfect_match' "
                    "or 'identity' (default: perfect_match)"
                )
            )
        ]
    )

    def get_queryset(self):
        assembly_accession = self.kwargs["assembly_accession"]

        # alignment type must be either 'identity' or 'perfect_match', default to latter
        alignment_type = self.request.query_params.get('type', 'perfect_match')
        if alignment_type not in ('identity', 'perfect_match'):
            raise Http404('Invalid alignment type')

        try:
            alignment_run = AlignmentRun.objects.filter(
                release_mapping_history__ensembl_species_history__assembly_accession__iexact=assembly_accession,  # pylint: disable=line-too-long
                score1_type=alignment_type
            ).latest('alignment_run_id')
        except (AlignmentRun.DoesNotExist, IndexError):
            raise Http404

        return Alignment.objects.filter(
            alignment_run=alignment_run
        ).order_by('alignment_id')
