from django.db import models
from core.models import AbstractBaseModel, Canvas


def get_segmentation_raw_upload_path(instance, filename):
    """Store raw segmentation files in tmp_images for processing"""
    # Use a simple filename to avoid path length issues
    import os
    ext = os.path.splitext(filename)[1]
    return f"tmp_images/{instance.canvas.id}/segmentations/{instance.id}/raw{ext}"


def get_segmentation_compressed_upload_path(instance, filename):
    """Store compressed PNG files in permanent storage"""
    return f"segmentations/{instance.canvas.id}/{instance.id}/{filename}"


def get_segmentation_dzi_upload_path(instance, filename):
    """Store DZI info.json files in tmp_images"""
    return f"tmp_images/{instance.canvas.id}/segmentations/{instance.id}/{filename}"


class SegmentationFile(AbstractBaseModel):
    """
    Model for storing uploaded segmentation files (.tif, .tiff, .png)
    Can be either probability maps (0-1) or label maps
    """
    
    class UploadType(models.TextChoices):
        PROBABILITY = "probability", "Probability Map"
        LABEL = "label", "Label Map"
    
    class Status(models.TextChoices):
        UPLOADING = "uploading", "Uploading"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
    
    canvas = models.ForeignKey(
        Canvas, on_delete=models.CASCADE, related_name="segmentation_files"
    )
    name = models.CharField(
        max_length=100,
        help_text="Type of segmentation (e.g., 'mitochondria', 'cells')"
    )
    raw_file = models.FileField(
        upload_to=get_segmentation_raw_upload_path,
        max_length=500,
        help_text="Raw uploaded segmentation file (TIFF or PNG) - deleted after processing"
    )
    file = models.FileField(
        upload_to=get_segmentation_compressed_upload_path,
        max_length=500,
        blank=True,
        null=True,
        help_text="Segmentation file (compressed PNG)"
    )
    dzi_file = models.FileField(
        upload_to=get_segmentation_dzi_upload_path,
        max_length=500,
        blank=True,
        null=True,
        help_text="DZI info.json file for viewing"
    )
    sobel_dzi_file = models.FileField(
        upload_to=get_segmentation_dzi_upload_path,
        max_length=500,
        blank=True,
        null=True,
        help_text="DZI info.json file for Sobel edge detection"
    )
    sam2_dzi_file = models.FileField(
        upload_to=get_segmentation_dzi_upload_path,
        max_length=500,
        blank=True,
        null=True,
        help_text="DZI info.json file for SAM2 segmentation"
    )
    upload_type = models.CharField(
        max_length=20,
        choices=UploadType.choices,
        default=UploadType.PROBABILITY
    )
    
    # Parameters for probability maps
    threshold = models.FloatField(
        null=True, 
        blank=True,
        help_text="Threshold value for probability maps (0-1)"
    )
    min_area = models.FloatField(
        null=True, 
        blank=True,
        help_text="Minimum area for objects after hole filling (in pixels)"
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADING
    )
    
    # Progress tracking (0-100)
    progress = models.IntegerField(default=0)
    progress_message = models.CharField(max_length=200, blank=True, default="")
    
    # Store any processing errors or metadata
    processing_info = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.canvas.name} - {self.name} ({self.get_upload_type_display()})"
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["canvas"]),
            models.Index(fields=["status"]),
        ]


class CanvasSegmentedObj(AbstractBaseModel):
    """
    Model for individual segmented objects extracted from segmentation files
    Can represent cells, organelles, or any other segmented structures
    """
    
    canvas = models.ForeignKey(
        Canvas, on_delete=models.CASCADE, related_name="segmented_objects"
    )
    source_file = models.ForeignKey(
        SegmentationFile, on_delete=models.CASCADE, related_name="segmented_objects"
    )
    name = models.CharField(
        max_length=100,
        help_text="Object type (e.g., 'mitochondria', 'cell')"
    )
    
    # Polygon stored as list of [x, y] coordinate pairs
    polygon = models.JSONField(
        help_text="List of [x, y] coordinate pairs defining the object boundary"
    )
    
    # Object properties
    area = models.FloatField(help_text="Area of the object in pixels")
    
    # For hierarchical relationships (e.g., mitochondria within cells)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
        help_text="Parent object (e.g., cell containing this organelle)"
    )
    
    # Original label ID from label map (if applicable)
    label_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Original label ID from label map"
    )
    
    # Additional properties
    centroid = models.JSONField(
        null=True,
        blank=True,
        help_text="[x, y] coordinates of object centroid"
    )
    bbox = models.JSONField(
        null=True,
        blank=True,
        help_text="Bounding box as [min_x, min_y, max_x, max_y]"
    )
    
    def __str__(self):
        parent_str = f" (in {self.parent.name} {self.parent.id})" if self.parent else ""
        return f"{self.name} - {self.canvas.name}{parent_str}"
    
    class Meta:
        ordering = ["name", "-area"]
        indexes = [
            models.Index(fields=["canvas"]),
            models.Index(fields=["source_file"]),
            models.Index(fields=["name"]),
            models.Index(fields=["parent"]),
        ]