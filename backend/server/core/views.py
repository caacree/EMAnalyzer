import os
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response

from image.tasks import convert_to_dzi_format
from core.tasks import prep_canvas
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

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a canvas and check if preparation is needed.
        If DZI files are missing, trigger prep_canvas task.
        """
        canvas = self.get_object()

        # Check if canvas needs preparation
        needs_prep = self._check_canvas_needs_prep(canvas)

        if needs_prep:
            print(f"Canvas {canvas.id} needs preparation, triggering prep_canvas task")
            prep_canvas.delay(str(canvas.id))

        return super().retrieve(request, *args, **kwargs)

    def _check_canvas_needs_prep(self, canvas):
        """
        Check if canvas DZI files are missing.

        Returns:
            bool: True if any required files are missing
        """
        # Check EM image DZI files
        for em_image in canvas.images.all():
            dzi_path = os.path.join(
                settings.MEDIA_ROOT,
                "tmp_images",
                str(canvas.id),
                str(em_image.id),
                "info.json"
            )
            if not os.path.exists(dzi_path):
                print(f"Missing EM DZI for image {em_image.id}")
                return True

        # Check MIMS overlay DZI files
        for mims_set in canvas.mims_sets.all():
            # Only check if there are MIMS images
            if not mims_set.mims_images.exists():
                continue

            # Check if overlays exist
            overlays = mims_set.overlays.all()
            if not overlays.exists():
                print(f"No overlays found for MIMS set {mims_set.id}")
                return True

            # Check if overlay DZI files exist
            for overlay in overlays:
                if overlay.mosaic:
                    dzi_path = os.path.join(settings.MEDIA_ROOT, overlay.mosaic)
                    if not os.path.exists(dzi_path):
                        print(f"Missing overlay DZI for MIMS set {mims_set.id}, isotope {overlay.isotope.name}")
                        return True

        return False

    @action(detail=True, methods=["get"])
    def prepare_for_gui(self, request, pk=None):
        canvas = get_object_or_404(Canvas, pk=pk)
        canvas_folder = os.path.join(settings.MEDIA_ROOT, "tmp_images", str(canvas.id))
        if not os.path.exists(canvas_folder):
            os.makedirs(canvas_folder)
        for image in canvas.images.all():
            image_path = os.path.join(canvas_folder, str(image.id))
            convert_to_dzi_format.delay(image.id, image_path)
        return Response(status=status.HTTP_200_OK)
