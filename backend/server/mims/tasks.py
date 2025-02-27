from celery import shared_task
import json
from django.apps import apps
from django.conf import settings
import SimpleITK as sitk
from django.shortcuts import get_object_or_404
from mims.services.register import register_images
from mims.services.orient_images import largest_inner_square
from mims.services.registration_utils import (
    create_registration_images,
)
from mims.model_utils import (
    get_concatenated_image,
)
from mims.models import Isotope, MIMSAlignment, MIMSImage
from skimage import exposure
import sims
import os

os.environ["VIPS_WARNING"] = "0"
from PIL import Image
from scipy import ndimage
from django.conf import settings
import numpy as np
from pystackreg import StackReg
from pystackreg.util import to_uint16
import pyvips
from mims.services import create_alignment_estimates, unwarp_image


@shared_task
def preprocess_mims_image_set(mims_image_set_id):
    MIMSImageSet = apps.get_model("mims", "MIMSImageSet")
    mims_image_set = MIMSImageSet.objects.get(id=mims_image_set_id)

    media_root = settings.MEDIA_ROOT

    image_dts = {}

    possible_12c_names = ["12C", "12C2"]
    possible_13c_names = ["13C", "12C 13C"]
    possible_15n_names = ["15N 12C", "12C 15N"]
    possible_14n_names = ["14N 12C", "12C 14N"]

    for mims_image in mims_image_set.mims_images.all():
        short_name = mims_image.file.name.split("/")[-1]
        print(f"Processing image {short_name}")
        mims = sims.SIMS(mims_image.file.path)
        is_valid_file = (
            mims and (mims.data is not None) and (mims.data.species is not None)
        )
        if not is_valid_file:
            mims_image.status = "INVALID_FILE"
            mims_image.save()
            continue
        mims_meta = mims.header["Image"]
        mims_pixel_size = mims_meta["raster"] / mims_meta["width"]
        mims_image.pixel_size_nm = mims_pixel_size
        mims_image.save()
        all_species = mims.data.species.values

        image_dts[mims_image.id] = mims.header["date"]

        # Define the path for saving
        isotope_image_dir = os.path.join(
            os.path.dirname(mims_image.file.path),
            mims_image.file.name.split(".")[0].split("/")[-1],
            "isotopes",
        )
        if not os.path.exists(isotope_image_dir):
            os.makedirs(isotope_image_dir)
        for species in all_species:
            iso = Isotope.objects.get_or_create(name=species)
            mims_image.isotopes.add(iso[0])
            # Extract and save the isotope image as a png
            sr = StackReg(StackReg.AFFINE)
            sr.register_stack(mims.data.loc[species].to_numpy(), reference="previous")
            stacked = sr.transform_stack(mims.data.loc[species].to_numpy())
            stacked = to_uint16(stacked)
            species_summed = stacked.sum(axis=0)
            species_summed = ndimage.median_filter(species_summed, size=1).astype(
                np.uint16
            )
            image_path = os.path.join(isotope_image_dir, f"{species}.png")
            img = Image.fromarray(species_summed)
            img.save(image_path)
            vmin, vmax = np.percentile(species_summed, (1, 99))
            autocontrast = exposure.rescale_intensity(
                species_summed, in_range=(vmin, vmax), out_range=(0, 255)
            ).astype(np.uint8)
            autocontrast_path = os.path.join(
                isotope_image_dir, f"{species}_autocontrast.png"
            )
            img = Image.fromarray(autocontrast)
            img.save(autocontrast_path)
        species_12c = next(
            (name for name in possible_12c_names if name in all_species), None
        )
        species_13c = next(
            (name for name in possible_13c_names if name in all_species), None
        )
        if species_12c and species_13c:
            c12_im = np.copy(
                np.asarray(
                    Image.open(os.path.join(isotope_image_dir, f"{species_12c}.png"))
                )
            )
            c13_im = np.asarray(
                Image.open(os.path.join(isotope_image_dir, f"{species_13c}.png"))
            )
            c12_im[c12_im == 0] = 1
            ratio = Image.fromarray(
                (np.divide(c13_im, c12_im) * 10000).astype(np.uint16)
            )
            ratio.save(os.path.join(isotope_image_dir, "13C12C_ratio.png"))

        species_15n = next(
            (name for name in possible_15n_names if name in all_species), None
        )
        species_14n = next(
            (name for name in possible_14n_names if name in all_species), None
        )
        if species_15n and species_14n:
            n15_im = np.copy(
                np.asarray(
                    Image.open(os.path.join(isotope_image_dir, f"{species_15n}.png"))
                )
            )
            n14_im = np.copy(
                np.asarray(
                    Image.open(os.path.join(isotope_image_dir, f"{species_14n}.png"))
                )
            )
            n14_im[n14_im == 0] = 1
            ratio = Image.fromarray(
                (np.divide(n15_im, n14_im) * 10000).astype(np.uint16)
            )
            ratio.save(os.path.join(isotope_image_dir, "15N14N_ratio.png"))
        mims_image.status = "PREPROCESSED"
        mims_image.save()

    # Use the image dts to determine priority number, earlier being better and save as image_set_priority on the mims_image
    ordered_dts = sorted(image_dts.items(), key=lambda x: x[1])
    for i, (mims_image_id, _) in enumerate(ordered_dts):
        mims_image = MIMSImage.objects.get(id=mims_image_id)
        mims_image.image_set_priority = i
        mims_image.save()

    # Now create the composite images
    isotopes = [i.name for i in mims_image_set.mims_images.first().isotopes.all()]
    species_12c = next((name for name in possible_12c_names if name in isotopes), None)
    species_13c = next((name for name in possible_13c_names if name in isotopes), None)
    if species_12c and species_13c:
        isotopes.append("13C12C_ratio")
    species_15n = next((name for name in possible_15n_names if name in isotopes), None)
    species_14n = next((name for name in possible_14n_names if name in isotopes), None)
    if species_15n and species_14n:
        isotopes.append("15N14N_ratio")
    for isotope in isotopes:
        relative_dir = os.path.join(
            "mims_image_sets",
            str(mims_image_set.id),
            "composites",
            "isotopes",
        )
        output_dir = os.path.join(settings.MEDIA_ROOT, relative_dir)

        os.makedirs(output_dir, exist_ok=True)
        img = get_concatenated_image(mims_image_set, isotope)
        img = pyvips.Image.new_from_array(img)

        id_url = os.path.join("http://localhost:8000/media", relative_dir)

        # Save the DZI file directly to the target directory
        if img.width <= 512 and img.height <= 512:
            img.dzsave(
                os.path.join(output_dir, isotope + ".dzi"),
                id=id_url,
                tile_size=512,
                depth="one",
                layout=pyvips.enums.ForeignDzLayout.IIIF3,
            )
        else:
            img.dzsave(
                os.path.join(output_dir, isotope + ".dzi"),
                id=id_url,
                layout=pyvips.enums.ForeignDzLayout.IIIF3,
            )

    print("MIMS image set preprocessing completed")


@shared_task
def estimate_mims_alignment(mims_image_id):
    MIMSImage = apps.get_model("mims", "MIMSImage")
    mims_image = MIMSImage.objects.get(id=mims_image_id)
    if mims_image.status in [
        "ESTIMATING_ALIGNMENTS_FROM_SET",
        "ESTIMATED_ALIGNMENTS_FROM_SET",
        "AWAITING_USER_ALIGNMENT",
        "CALCULATING_FINAL_ALIGNMENT",
        "COMPLETE",
    ]:
        return
    # See if there are any images from the set with confirmed alignments
    confirmed_aligned_images = mims_image.image_set.mims_images.filter(
        status__in=[
            "AWAITING_USER_ALIGNMENT",
            "CALCULATING_FINAL_ALIGNMENT",
            "COMPLETE",
        ]
    ).exclude(id=mims_image.id)
    if confirmed_aligned_images.exists():
        confirmed_alignment = (
            confirmed_aligned_images.first()
            .alignments.filter(status__in=["ROUGH", "COMPLETE"])
            .first()
        )
        mims_image.status = "ESTIMATING_ALIGNMENTS_FROM_SET"
        mims_image.save()
        create_alignment_estimates(
            mims_image,
            confirmed_alignment,
        )
        mims_image.status = "ESTIMATED_ALIGNMENTS_FROM_SET"
        mims_image.save()
    else:
        mims_image.status = "ESTIMATING_ALIGNMENTS_INITIAL"
        mims_image.save()
        create_alignment_estimates(mims_image)
        mims_image.status = "ESTIMATED_ALIGNMENTS_INITIAL"
        mims_image.save()


@shared_task
def unwarp_image_task(mims_image_obj_id):
    mims_image = get_object_or_404(MIMSImage, pk=mims_image_obj_id)
    mims_image.status = "DEWARPING"
    mims_image.save()
    unwarp_image(mims_image)
    mims_image.status = "DEWARPED_ALIGNED"
    mims_image.save()


@shared_task
def create_registration_images_task(mims_image_obj_id):
    mims_image = get_object_or_404(MIMSImage, pk=mims_image_obj_id)
    create_registration_images(mims_image)
    mims_image.status = "AWAITING_REGISTRATION"
    mims_image.save()


@shared_task
def register_images_task(mims_image_obj_id):
    register_images(mims_image_obj_id)
