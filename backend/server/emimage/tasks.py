from celery import shared_task
from django.apps import apps
from django.conf import settings
import pyvips
import os


@shared_task
def convert_to_dzi_format(em_image_id):
    EMImage = apps.get_model("emimage", "EMImage")
    em_image = EMImage.objects.get(id=em_image_id)
    img = pyvips.Image.new_from_file(em_image.file.path, access="sequential")

    # Define the target directory and create it if it does not exist
    target_dir = os.path.join("media", "em_images", str(em_image.id), "converted")
    os.makedirs(target_dir, exist_ok=True)

    # Create a filename for the DZI file
    iiif_full_dirpath = os.path.join(
        settings.MEDIA_ROOT, "em_images", str(em_image.id), "converted"
    )
    # Construct the correct id URL for the DZI file
    id_url = f"http://localhost:8000{settings.MEDIA_URL}{os.path.join(
        "em_images", str(em_image.id))}"

    # Save the DZI file directly to the target directory
    img.dzsave(
        iiif_full_dirpath,
        id=id_url,
        layout=pyvips.enums.ForeignDzLayout.IIIF3,
    )

    # Update the dzi_file field in the EMImage model
    em_image.dzi_file.name = os.path.join(
        "em_images", str(em_image.id), "converted", "info.json"
    )
    em_image.save()

    print("DZI conversion completed")
