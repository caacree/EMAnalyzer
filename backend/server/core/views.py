import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response

from image.tasks import convert_to_dzi_format
from .models import Canvas
from .serializers import CanvasListSerializer, CanvasDetailSerializer

TEMP_DIR = "../tmp_images"


class CanvasViewSet(viewsets.ModelViewSet):
    queryset = Canvas.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return CanvasListSerializer
        if self.action == "retrieve":
            return CanvasDetailSerializer
        return CanvasListSerializer

    @action(detail=True, methods=["get"])
    def prepare_for_gui(self, request, pk=None):
        canvas = get_object_or_404(Canvas, pk=pk)
        canvas_folder = os.path.join(settings.MEDIA_ROOT, "tmp_images", str(canvas.id))
        if not os.path.exists(canvas_folder):
            os.makedirs(canvas_folder)
        for image in canvas.images.all():
            image_path = os.path.join(canvas_folder, str(image.id))
            # convert_to_dzi_format.delay(image.id, image_path)
        return Response(status=status.HTTP_200_OK)
