from django.db import models
from core.models import AbstractBaseModel, CanvasObj, Canvas
from PIL import Image
import os
import shutil
from image.tasks import convert_to_dzi_format

Image.MAX_IMAGE_PIXELS = None


def get_em_image_upload_path(instance, filename):
    """Store raw EM images organized by image ID"""
    return f"em_images/{instance.id}/{filename}"


def get_dzi_image_upload_path(instance, filename):
    """Store DZI files in tmp_images organized by canvas and image"""
    return f"tmp_images/{instance.canvas.id}/{instance.id}/{filename}"


class ViewStatus(models.IntegerChoices):
    NO_FILE = 0
    UNPROCESSED = 1
    PROCESSING = 2
    READY = 3


class Image(CanvasObj):
    file = models.FileField(upload_to=get_em_image_upload_path)
    dzi_file = models.ImageField(
        upload_to=get_dzi_image_upload_path, blank=True, null=True
    )
    canvas = models.ForeignKey(Canvas, on_delete=models.CASCADE, related_name="images")
    friendly_name = models.CharField(max_length=255, null=True, blank=True)

    view_status = models.IntegerField(
        choices=ViewStatus.choices, default=ViewStatus.UNPROCESSED
    )

    def __str__(self):
        return self.file.path

    @property
    def file_url(self):
        return self.file.url

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            # Try and get the pixel size from the image metadata
            try:
                with Image.open(self.file.path) as img:
                    self.pixel_size_nm = float(img.tag_v2.get(0x828D, [0])[0])
                    super().save(update_fields=["pixel_size_nm"])
            except Exception:
                pass
            convert_to_dzi_format.delay(self.id)

    def delete(self, *args, **kwargs):
        # Delete the media directory with the EM image files
        if self.file:
            dir_path = os.path.dirname(self.file.path)
            if os.path.isdir(dir_path):
                shutil.rmtree(dir_path)
        super().delete(*args, **kwargs)
