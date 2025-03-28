from django.db import models
from core.models import AbstractBaseModel, CanvasObj, Canvas
import os
import shutil
from mims.model_utils import get_concatenated_image
from django.conf import settings


def get_mims_image_upload_path(instance, filename):
    return f"mims_image_sets/{instance.image_set.id}/mims_images/{filename}"


class Isotope(AbstractBaseModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class MIMSImageSet(CanvasObj):
    canvas = models.ForeignKey(
        Canvas, on_delete=models.CASCADE, related_name="mims_sets"
    )
    status = models.CharField(max_length=50, default="PREPROCESSING")

    def __str__(self):
        return f"{self.canvas.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def delete(self, *args, **kwargs):
        # Delete the media directory with the image files
        if os.path.exists(
            os.path.join(settings.MEDIA_ROOT, "mims_image_sets", str(self.id))
        ):
            shutil.rmtree(
                os.path.join(settings.MEDIA_ROOT, "mims_image_sets", str(self.id))
            )
        super().delete(*args, **kwargs)

    def get_canvas_composite(self, isotope):
        if not isotope:
            isotopes = self.mims_images.first().isotopes.all()
            if not isotopes:
                return None
            if "SE" in isotopes:
                isotope = "SE"
            else:
                isotope = isotopes[0]
        return get_concatenated_image(self, isotope)


class MIMSImage(CanvasObj):
    name = models.CharField(max_length=50, default="")
    canvas = models.ForeignKey(Canvas, on_delete=models.CASCADE, related_name="mims")
    image_set = models.ForeignKey(
        MIMSImageSet, related_name="mims_images", on_delete=models.CASCADE
    )
    image_set_priority = models.IntegerField(default=0)
    # Status options are:
    # - "PREPROCESSING" for not yet processed
    # - "PREPROCESSED" for processed and ready for alignment
    # - "ESTIMATING_ALIGNMENTS_INITIAL" for currently generating estimates
    # - "ESTIMATED_ALIGNMENTS_INITIAL" for alignment estimates ready, awaiting user selection
    # - "ESTIMATING_ALIGNMENTS_FROM_SET" for currently generating estimates from the set
    # - "ESTIMATED_ALIGNMENTS_FROM_SET" for alignment estimates ready, awaiting user selection
    # - "AWAITING_USER_ALIGNMENT" for user confirmed location (either manual or from an estimate)
    #    and need user to select points / shapes
    # - "CALCULATING_FINAL_ALIGNMENT" for processing final alignment after user-selected points
    # - "COMPLETE" for final alignment after user-selected points
    status = models.CharField(max_length=50, default="PREPROCESSING")
    file = models.FileField(upload_to=get_mims_image_upload_path)
    isotopes = models.ManyToManyField(Isotope)

    def __str__(self):
        filename = self.name if self.name else self.file.name.split("/")[-1]
        return f"{self.canvas.name} - {filename}"

    def __repr__(self):
        filename = self.name if self.name else self.file.name.split("/")[-1]
        return f"{self.canvas.name} - {filename}"

    def delete(self, *args, **kwargs):
        # Delete the media directory with the image files
        if self.file:
            os.remove(self.file.path)
        super().delete(*args, **kwargs)


class MIMSAlignment(AbstractBaseModel):
    # Status options are:
    # - "ESTIMATE_INITIAL" for made from no info
    # - "ESTIMATE_FROM_SET" for made from previous alignment
    # - "ROUGH" for user confirmed location (either manual or from an estimate)
    # - "COMPLETE" for final alignment after user-selected points
    status = models.CharField(max_length=50, default="ESTIMATE_INITIAL")
    mims_image = models.ForeignKey(
        MIMSImage, on_delete=models.CASCADE, related_name="alignments"
    )
    # x and y offset are from the top left of the original EM image
    x_offset = models.IntegerField()
    y_offset = models.IntegerField()
    rotation_degrees = models.IntegerField()
    flip_hor = models.BooleanField()
    scale = models.FloatField()

    info = models.JSONField(null=True, blank=True)
