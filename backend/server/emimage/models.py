from django.db import models
from core.models import AbstractBaseModel
from PIL import Image
import os
import shutil
from emimage.tasks import convert_to_dzi_format

Image.MAX_IMAGE_PIXELS = None


def get_em_image_upload_path(instance, filename):
    if instance.id:
        return f"em_images/{instance.id}/{filename}"
    return f"em_images/temp/{filename}"


def get_dzi_image_upload_path(instance, filename):
    if instance.id:
        return f"em_images/{instance.id}/converted/{filename}"
    return f"em_images/temp/converted/{filename}"


class EMImage(AbstractBaseModel):
    file = models.FileField(upload_to=get_em_image_upload_path)
    dzi_file = models.ImageField(
        upload_to=get_dzi_image_upload_path, blank=True, null=True
    )
    friendly_name = models.CharField(max_length=255)
    pixel_size_nm = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.file.path

    @property
    def file_url(self):
        return self.file.url

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_file_path = self.file.path if not is_new else None
        super().save(*args, **kwargs)
        if not is_new and self.file and not self.dzi_file:
            # Update file paths after initial save to use the correct ID-based paths
            new_file_path = get_em_image_upload_path(
                self, os.path.basename(self.file.name)
            )
            new_dzi_file_path = get_dzi_image_upload_path(
                self, os.path.basename(self.file.name)
            )
            if self.file.name != new_file_path:
                self.file.name = new_file_path
                self.dzi_file.name = new_dzi_file_path
                self.save(update_fields=["file", "dzi_file"])
                # Cleanup the old temporary file if it exists
                if old_file_path and os.path.isfile(old_file_path):
                    os.remove(old_file_path)
            convert_to_dzi_format.delay(self.id)
        if is_new:
            # Try and get the pixel size from the image metadata
            try:
                with Image.open(self.file.path) as img:
                    self.pixel_size_nm = float(img.tag_v2.get(0x828D, [0])[0])
            except Exception:
                pass

    def delete(self, *args, **kwargs):
        # Delete the media directory with the EM image files
        if self.file:
            dir_path = os.path.dirname(self.file.path)
            if os.path.isdir(dir_path):
                shutil.rmtree(dir_path)
        super().delete(*args, **kwargs)
