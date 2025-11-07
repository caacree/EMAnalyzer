from rest_framework import serializers
from mims.models import MIMSImageSet, MIMSOverlay
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


class MimsOverlaySerializer(serializers.ModelSerializer):
    isotope = serializers.SerializerMethodField()
    dzi_url = serializers.SerializerMethodField()

    class Meta:
        model = MIMSOverlay
        fields = ["id", "isotope", "dzi_url"]

    def get_isotope(self, obj):
        return obj.isotope.name

    def get_dzi_url(self, obj):
        if obj.mosaic:
            return os.path.join(settings.MEDIA_URL, obj.mosaic)
        return None


class MimsImageSetCanvasDetailSerializer(serializers.ModelSerializer):
    mims_overlays = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    mims_images = serializers.SerializerMethodField()

    class Meta:
        model = MIMSImageSet
        depth = 2
        fields = [
            "id",
            "canvas",
            "status",
            "created_at",
            "updated_at",
            "flip",
            "rotation_degrees",
            "canvas_bbox",
            "pixel_size_nm",
            "mims_images",
            "mims_overlays",
        ]

    def get_status(self, obj):
        return obj.get_status_display()

    def get_mims_images(self, obj):
        from mims.serializers import MIMSImageSerializer

        return MIMSImageSerializer(obj.mims_images.all(), many=True).data

    def get_mims_overlays(self, obj):
        return MimsOverlaySerializer(obj.overlays.all(), many=True).data


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
