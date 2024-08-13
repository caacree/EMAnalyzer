# serializers.py

from rest_framework import serializers
from emimage.models import EMImage
import os
from pathlib import Path
from django.conf import settings
from mims.models import MIMSImageSet, MIMSImage, Isotope


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


class MIMSImageSerializer(serializers.ModelSerializer):
    isotopes = serializers.SerializerMethodField()

    class Meta:
        model = MIMSImage
        fields = [
            "id",
            "image_set",
            "file",
            "pixel_size_nm",
            "created_at",
            "updated_at",
            "isotopes",
            "status",
        ]

    def get_isotopes(self, obj):
        isotopes = obj.isotopes.all()
        return IsotopeImageSerializer(
            isotopes,
            many=True,
            context={"request": self.context.get("request"), "mims_image": obj},
        ).data


class MIMSImageSetSerializer(serializers.ModelSerializer):
    mims_images = MIMSImageSerializer(many=True, read_only=True)
    composite_images = serializers.SerializerMethodField()

    class Meta:
        model = MIMSImageSet
        fields = [
            "id",
            "em_image",
            "mims_images",
            "created_at",
            "updated_at",
            "composite_images",
            "flip",
            "rotation_degrees",
            "em_coordinates_x",
            "em_coordinates_y",
            "em_scale",
        ]
        depth = 1

    def get_composite_images(self, obj):
        relative_dir = os.path.join(
            "mims_image_sets",
            str(obj.id),
            "composites",
            "isotopes",
        )
        composites_dir = os.path.join(
            settings.MEDIA_ROOT,
            relative_dir,
        )
        # Get all the images in the directory
        composite_images = []
        if Path(composites_dir).exists():
            composite_images = [
                f.split(".")[0]
                for f in os.listdir(composites_dir)
                if f.endswith(".dzi")
            ]
        # Make an object where the key is the isotope name and the value is the url
        composite_images = {
            isotope_name: os.path.join(
                "http://localhost:8000/media", relative_dir, isotope_name + ".dzi"
            )
            for isotope_name in composite_images
        }
        return composite_images


class EMImageSerializer(serializers.ModelSerializer):
    mims_sets = MIMSImageSetSerializer(
        many=True, read_only=True, source="mimsimageset_set"
    )

    class Meta:
        model = EMImage
        fields = [
            "id",
            "file",
            "dzi_file",
            "pixel_size_nm",
            "friendly_name",
            "created_at",
            "updated_at",
            "mims_sets",
        ]
