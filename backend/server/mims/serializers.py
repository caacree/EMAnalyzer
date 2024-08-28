# mims/serializers.py

from rest_framework import serializers
from django.conf import settings
import os
from image.models import Image
from mims.models import MIMSImageSet, MIMSImage, Isotope, MIMSAlignment
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

        file_path = os.path.join(
            "mims_images",
            str(mims_image_set.id),
            str(mims_image.id),
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


class MIMSImageSetSerializer(serializers.ModelSerializer):
    composite_images = serializers.SerializerMethodField()

    class Meta:
        model = MIMSImageSet
        depth = 1
        fields = [
            "id",
            "canvas",
            "created_at",
            "updated_at",
            "composite_images",
            "flip",
            "rotation_degrees",
            "canvas_x",
            "canvas_y",
            "pixel_size_nm",
            "mims_images",
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


# Import MIMSAlignment model
from mims.models import MIMSImageSet, MIMSImage, Isotope, MIMSAlignment


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


# Update MIMSImageSerializer to include alignments
class MIMSImageSerializer(serializers.ModelSerializer):
    isotopes = serializers.SerializerMethodField()
    image_set = MIMSImageSetSerializer(read_only=True)
    alignments = MIMSAlignmentSerializer(
        many=True, read_only=True
    )  # Include alignments

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
            "alignments",
        ]

    def get_isotopes(self, obj):
        isotopes = obj.isotopes.all()
        return IsotopeImageSerializer(
            isotopes,
            many=True,
            context={"request": self.context.get("request"), "mims_image": obj},
        ).data
