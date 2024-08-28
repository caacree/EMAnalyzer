from rest_framework import serializers
from mims.models import MIMSImageSet
from core.models import Canvas
import os
from pathlib import Path
from django.conf import settings


class CanvasListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Canvas
        fields = [
            "id",
            "name",
            "width",
            "height",
            "pixel_size_nm",
            "mims_sets",
            "images",
            "created_at",
            "updated_at",
        ]


class MimsImageSetCanvasDetailSerializer(serializers.ModelSerializer):
    composite_images = serializers.SerializerMethodField()

    class Meta:
        model = MIMSImageSet
        depth = 1
        fields = [
            "id",
            "canvas",
            "created_at",
            "updated_at",
            "flip",
            "rotation_degrees",
            "composite_images",
            "canvas_x",
            "canvas_y",
            "pixel_size_nm",
            "mims_images",
        ]

    def get_composite_images(self, obj):
        composites_dir = os.path.join(
            settings.MEDIA_ROOT,
            "mims_image_sets",
            str(obj.id),
            "composites",
            "isotopes",
        )
        # Get all the images in the directory
        composite_images = []
        if Path(composites_dir).exists():
            dzi_folders = [f for f in os.listdir(composites_dir) if f.endswith(".dzi")]
        # Make an object where the key is the isotope name and the value is the url
        composite_images = {
            folder.split(".")[0]: os.path.join(
                settings.MEDIA_URL,
                "mims_image_sets",
                str(obj.id),
                "composites",
                "isotopes",
                folder,
            )
            for folder in dzi_folders
        }
        return composite_images


class CanvasDetailSerializer(serializers.ModelSerializer):
    mims_sets = MimsImageSetCanvasDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Canvas
        depth = 1
        fields = [
            "id",
            "name",
            "width",
            "height",
            "pixel_size_nm",
            "mims_sets",
            "images",
            "created_at",
            "updated_at",
        ]
