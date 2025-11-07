# serializers.py

from rest_framework import serializers
from image.models import Image
import os
from pathlib import Path
from django.conf import settings
from mims.models import MIMSImageSet, MIMSImage, Isotope
from PIL import Image as PILImage
from django.core.files.base import ContentFile
import io
import tempfile

PILImage.MAX_IMAGE_PIXELS = None


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
            "status",
            "canvas",
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
        canvas_id = str(obj.canvas.id)
        relative_dir = os.path.join(
            "tmp_images",
            canvas_id,
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
                settings.MEDIA_URL, relative_dir, isotope_name + ".dzi"
            )
            for isotope_name in composite_images
        }
        return composite_images


class ImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = Image
        fields = [
            "id",
            "canvas",
            "file",
            "dzi_file",
            "pixel_size_nm",
            "friendly_name",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        """Convert uploaded image to compressed PNG before saving"""
        file_obj = validated_data.get("file")

        if file_obj:
            # Save to temporary location to read it
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(file_obj.name)[1]
            ) as temp_file:
                for chunk in file_obj.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

            try:
                # Open and convert to PNG
                with PILImage.open(temp_path) as img:
                    # Convert to RGB or grayscale as appropriate
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    elif img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")

                    # Save to PNG in memory with compression
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG", optimize=True, compress_level=6)
                    buffer.seek(0)

                    # Get the original filename and change extension to .png
                    original_filename = os.path.basename(file_obj.name)
                    png_filename = os.path.splitext(original_filename)[0] + ".png"

                    # Replace the file with PNG version
                    validated_data["file"] = ContentFile(
                        buffer.read(), name=png_filename
                    )

            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        return super().create(validated_data)
