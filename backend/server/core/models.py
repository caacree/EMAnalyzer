from django.db import models
import uuid


class AbstractBaseModel(models.Model):
    """
    Base abstract model, that has `uuid` instead of `id` and includes `created_at`, `updated_at` fields.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, unique=True
    )
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    updated_at = models.DateTimeField("Updated at", auto_now=True)

    class Meta:
        abstract = True

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.id}>"


class Canvas(AbstractBaseModel):
    """
    Base model for a canvas that images are aligned to
    """

    name = models.CharField(max_length=50, unique=True)
    width = models.IntegerField(null=True)
    height = models.IntegerField(null=True)
    pixel_size_nm = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name or self.id


class CanvasObj(AbstractBaseModel):
    """
    Base model for images that are aligned to a canvas
    """

    flip = models.BooleanField(default=False)
    rotation_degrees = models.IntegerField(null=True)
    canvas_bbox = models.JSONField(null=True, help_text="Array of 4 [x,y] coordinates defining bounding box")
    pixel_size_nm = models.FloatField(null=True)
