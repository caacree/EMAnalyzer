from django.contrib import admin
from .models import MIMSImageSet, MIMSImage


@admin.register(MIMSImageSet)
class MIMSImageSetAdmin(admin.ModelAdmin):
    list_display = ("get_canvas_name", "created_at")
    list_filter = ("created_at", "updated_at", "canvas__name")
    search_fields = ("canvas__name",)

    def get_canvas_name(self, obj):
        return obj.canvas.name

    get_canvas_name.short_description = "Canvas"
    get_canvas_name.admin_order_field = "canvas__name"


@admin.register(MIMSImage)
class MIMSImageAdmin(admin.ModelAdmin):
    list_display = ("get_display_name", "get_canvas_name", "created_at")
    list_filter = ("created_at", "updated_at", "canvas__name")
    search_fields = ("canvas__name", "file")

    def get_canvas_name(self, obj):
        return obj.canvas.name

    get_canvas_name.short_description = "Canvas"
    get_canvas_name.admin_order_field = "canvas__name"

    def get_display_name(self, obj):
        return obj.name if obj.name else obj.file.name.split("/")[-1]

    get_display_name.short_description = "Name"
