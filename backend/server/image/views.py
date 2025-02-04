from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.decorators import action
from django.conf import settings
from .models import Image
from .serializers import ImageSerializer
from django.http import FileResponse
import os


class ImageViewSet(viewsets.ModelViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer

    @action(detail=True, methods=["get"])
    def dzi(self, request, pk=None):
        image = get_object_or_404(Image, pk=pk)
        canvas_folder = os.path.join(
            settings.MEDIA_ROOT, "tmp_images", str(image.canvas.id)
        )
        image_path = os.path.join(canvas_folder, str(image.id))

        if os.path.exists(image_path):
            return FileResponse(open(image_path, "rb"), content_type="application/xml")
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
