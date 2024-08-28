from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from core.models import Canvas
from .models import MIMSImageSet, MIMSImage, Isotope
from .serializers import MIMSImageSetSerializer, MIMSImageSerializer
from .tasks import preprocess_mims_image_set
from mims.services.orient_images import orient_viewset
import json
import pyvips
import os
from django.conf import settings
from mims.services.concat_utils import get_concatenated_image


class MIMSImageSetViewSet(viewsets.ModelViewSet):
    queryset = MIMSImageSet.objects.all()
    serializer_class = MIMSImageSetSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        canvas_id = data.get("canvas")
        canvas = Canvas.objects.get(id=canvas_id)
        image_set = MIMSImageSet.objects.create(canvas=canvas)

        for file_key in data.keys():
            if file_key.startswith("file_"):
                file = data[file_key]
                MIMSImage.objects.create(
                    canvas=canvas,
                    image_set=image_set,
                    file=file,
                )
        preprocess_mims_image_set.delay(image_set.id)

        serializer = MIMSImageSetSerializer(image_set)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit_viewset_alignment_points(self, request, pk=None):
        data = request.data
        mims_image_set = self.get_object()
        viewset_points = data.get("points")
        orient_viewset(mims_image_set, viewset_points)
        return Response(status=status.HTTP_200_OK)


class MIMSImageViewSet(viewsets.ModelViewSet):
    queryset = MIMSImage.objects.all()
    serializer_class = MIMSImageSerializer
