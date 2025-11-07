# mims/serializers.py

from rest_framework import serializers
from django.conf import settings
import os
from image.models import Image
from mims.models import (
    MIMSImageSet,
    MIMSImage,
    Isotope,
    MIMSAlignment,
    MIMSOverlay,
    MimsTiffImage,
)
from pathlib import Path


class IsotopeImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Isotope
        fields = ["name", "url"]

    def get_url(self, obj):
        request = self.context.get("request")
        mims_image = self.context.get("mims_image")
        mims_image_set = mims_image.image_set
        canvas_id = mims_image.canvas.id
        filename = os.path.basename(mims_image.file.name).split(".")[0]

        file_path = os.path.join(
            "tmp_images",
            str(canvas_id),
            str(mims_image_set.id),
            "mims_images",
            filename,
            "isotopes",
            obj.name + "_autocontrast.png",
        )

        url = os.path.join(settings.MEDIA_URL, file_path)
        return url


class MIMSOverlaySerializer(serializers.ModelSerializer):
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


class MIMSImageSetSerializer(serializers.ModelSerializer):
    mims_overlays = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = MIMSImageSet
        depth = 1
        fields = [
            "id",
            "status",
            "canvas",
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

    def get_mims_overlays(self, obj):
        return MIMSOverlaySerializer(obj.overlays.all(), many=True).data


# New serializer for MIMSAlignment
class MIMSAlignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MIMSAlignment
        fields = [
            "id",
            "status",
            "x_offset",
            "y_offset",
            "rotation_degrees",
            "flip_hor",
            "scale",
        ]


class MimsTiffImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MimsTiffImage
        fields = ["id", "name", "image", "registration_bbox"]


# Update MIMSImageSerializer to include alignments
class MIMSImageSerializer(serializers.ModelSerializer):
    isotopes = serializers.SerializerMethodField()
    image_set = MIMSImageSetSerializer(read_only=True)
    em_dzi = serializers.SerializerMethodField()
    registration = serializers.SerializerMethodField()
    mims_tiff_images = MimsTiffImageSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = MIMSImage
        fields = [
            "id",
            "status",
            "image_set",
            "file",
            "pixel_size_nm",
            "created_at",
            "updated_at",
            "isotopes",
            "canvas_bbox",
            "em_dzi",
            "registration",
            "mims_tiff_images",
        ]

    def get_status(self, obj):
        return obj.get_status_display()

    def get_isotopes(self, obj):
        isotopes = obj.isotopes.all()
        return IsotopeImageSerializer(
            isotopes,
            many=True,
            context={"request": self.context.get("request"), "mims_image": obj},
        ).data

    def get_em_dzi(self, obj):
        canvas = obj.image_set.canvas
        em_image = canvas.images.first()
        if em_image and em_image.dzi_file:
            return em_image.dzi_file.url

    def get_registration(self, obj):
        if obj.status != MIMSImage.Status.REGISTERING:
            return None
        isotopes = obj.isotopes.all()
        canvas_id = obj.canvas.id
        image_set_id = obj.image_set.id
        filename = os.path.basename(obj.file.name).split(".")[0]

        base = os.path.join(
            settings.MEDIA_URL,
            "tmp_images",
            str(canvas_id),
            str(image_set_id),
            "mims_images",
            filename,
            "registration"
        )
        suffix = ""

        urls = {
            "em_url": os.path.join(base, f"em{suffix}.png"),
        }
        for isotope in isotopes:
            urls[f"{isotope.name}_url"] = os.path.join(
                Path(base).parent, "isotopes", f"{isotope.name}_autocontrast.png"
            )
        return urls

    def get_unwarped_images(self, obj):
        return []
