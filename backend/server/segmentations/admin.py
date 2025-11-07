from django.contrib import admin
from .models import SegmentationFile, CanvasSegmentedObj


@admin.register(SegmentationFile)
class SegmentationFileAdmin(admin.ModelAdmin):
    list_display = ["name", "canvas", "upload_type", "status", "created_at"]
    list_filter = ["upload_type", "status", "canvas"]
    search_fields = ["name", "canvas__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    
    fieldsets = (
        (None, {
            "fields": ("id", "canvas", "file", "name", "upload_type", "status")
        }),
        ("Processing Parameters", {
            "fields": ("threshold", "min_area"),
            "description": "Parameters for probability map processing"
        }),
        ("Metadata", {
            "fields": ("processing_info", "created_at", "updated_at")
        })
    )


@admin.register(CanvasSegmentedObj)
class CanvasSegmentedObjAdmin(admin.ModelAdmin):
    list_display = ["name", "canvas", "area", "parent", "label_id", "created_at"]
    list_filter = ["name", "canvas", "source_file"]
    search_fields = ["name", "canvas__name"]
    readonly_fields = ["id", "created_at", "updated_at", "area", "centroid", "bbox"]
    raw_id_fields = ["parent", "source_file"]
    
    fieldsets = (
        (None, {
            "fields": ("id", "canvas", "source_file", "name", "parent")
        }),
        ("Geometry", {
            "fields": ("polygon", "area", "centroid", "bbox")
        }),
        ("Metadata", {
            "fields": ("label_id", "created_at", "updated_at")
        })
    )