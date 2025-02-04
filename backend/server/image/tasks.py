from celery import shared_task
from django.apps import apps
from django.conf import settings
import pyvips
import os


@shared_task
def convert_to_dzi_format(em_image_id, save_path=False):
    Image = apps.get_model("image", "Image")
    em_image = Image.objects.get(id=em_image_id)
    img = pyvips.Image.new_from_file(em_image.file.path, access="sequential")

    # Define the target directory and create it if it does not exist
    if not save_path:
        save_path = os.path.join(
            settings.MEDIA_ROOT, "tmp_images", str(em_image.canvas.id), str(em_image.id)
        )

    # Construct the correct id URL for the DZI file
    id_url = f"http://localhost:8000{settings.MEDIA_URL}{os.path.join(
        "tmp_images", str(em_image.canvas.id))}"

    # Save the DZI file directly to the target directory
    img.dzsave(
        save_path,
        id=id_url,
        layout=pyvips.enums.ForeignDzLayout.IIIF3,
    )

    # Update the dzi_file field in the Image model
    em_image.dzi_file.name = os.path.join(
        "tmp_images", str(em_image.canvas.id), str(em_image.id), "info.json"
    )
    em_image.save()

    print("DZI conversion completed")
