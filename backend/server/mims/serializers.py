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
        filename = os.path.basename(mims_image.file.name).split(".")[0]

        file_path = os.path.join(
            "mims_image_sets",
            str(mims_image_set.id),
            "mims_images",
            filename,
            "isotopes",
            obj.name + "_autocontrast.png",
        )

        if request:
            url = request.build_absolute_uri(
                os.path.join(settings.MEDIA_URL, file_path)
            )
        else:
            url = os.path.join(settings.MEDIA_URL, file_path)

        return url


class MIMSOverlaySerializer(serializers.ModelSerializer):
    isotope = serializers.SerializerMethodField()

    class Meta:
        model = MIMSOverlay
        fields = ["id", "isotope", "mosaic"]

    def get_isotope(self, obj):
        return obj.isotope.name


class MIMSImageSetSerializer(serializers.ModelSerializer):
    composite_images = serializers.SerializerMethodField()
    mims_overlays = serializers.SerializerMethodField()

    class Meta:
        model = MIMSImageSet
        depth = 1
        fields = [
            "id",
            "status",
            "canvas",
            "created_at",
            "updated_at",
            "composite_images",
            "flip",
            "rotation_degrees",
            "canvas_bbox",
            "pixel_size_nm",
            "mims_images",
            "mims_overlays",
        ]

    def get_composite_images(self, obj):
        composites_dir = os.path.join(
            settings.MEDIA_ROOT,
            "mims_images",
            str(obj.id),
            "composites",
            "isotopes",
        )
        # Get all the images in the directory
        composite_images = []
        if Path(composites_dir).exists():
            [f.split(".")[0] for f in os.listdir(composites_dir)]
        # Make an object where the key is the isotope name and the value is the url
        composite_images = {
            isotope_name: os.path.join(
                settings.MEDIA_URL,
                "mims_images",
                str(obj.id),
                "composites",
                "isotopes",
                isotope_name + ".png",
            )
            for isotope_name in composite_images
        }
        return composite_images

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
        if em_image:
            return "http://localhost:8000" + em_image.dzi_file.url

    def get_registration(self, obj):
        if obj.status != "AWAITING_REGISTRATION" and obj.status != "DEWARP PENDING":
            return None
        isotopes = obj.isotopes.all()
        filepath = Path(obj.file.name)
        base = os.path.join(
            settings.MEDIA_URL, filepath.parent, filepath.stem, "registration"
        )
        suffix = "_final" if obj.status == "DEWARP PENDING" else ""

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
