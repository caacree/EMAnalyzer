from django.db import models
from core.models import AbstractBaseModel
from emimage.models import EMImage
import os
import shutil


def get_mims_image_upload_path(instance, filename):
    return f"mims_image_sets/{instance.image_set.id}/mims_images/{filename}"


class Isotope(AbstractBaseModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class MIMSImageSet(AbstractBaseModel):
    em_image = models.ForeignKey(EMImage, on_delete=models.CASCADE)
    flip = models.BooleanField(default=False)
    rotation_degrees = models.IntegerField(null=True)
    em_coordinates_x = models.IntegerField(null=True)
    em_coordinates_y = models.IntegerField(null=True)
    em_scale = models.FloatField(null=True)

    def __str__(self):
        return f"MIMSImageSet {self.id}"

    def delete(self, *args, **kwargs):
        # Delete the media directory with the image files
        shutil.rmtree(os.path.join(settings.MEDIA_ROOT, "mims_image_sets", self.id))
        super().delete(*args, **kwargs)


class MIMSImage(AbstractBaseModel):
    image_set = models.ForeignKey(
        MIMSImageSet, related_name="mims_images", on_delete=models.CASCADE
    )
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
    pixel_size_nm = models.FloatField(blank=True, null=True)
    isotopes = models.ManyToManyField(Isotope)

    def __str__(self):
        return self.file.name

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
