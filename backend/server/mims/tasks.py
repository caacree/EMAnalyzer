from celery import shared_task
from django.apps import apps
from django.conf import settings
from mims.services.concat_utils import get_concatenated_image
from mims.models import Isotope
from skimage import exposure
import sims
import os
from PIL import Image
from scipy import ndimage
from django.conf import settings
import numpy as np
from pystackreg import StackReg
from pystackreg.util import to_uint16
import pyvips
from mims.services import create_alignment_estimates


@shared_task
def preprocess_mims_image_set(mims_image_set_id):
    MIMSImageSet = apps.get_model("mims", "MIMSImageSet")
    mims_image_set = MIMSImageSet.objects.get(id=mims_image_set_id)

    media_root = settings.MEDIA_ROOT

    for mims_image in mims_image_set.mims_images.all():
        print(f"doing image {mims_image.file.name}")
        mims = sims.SIMS(mims_image.file.path)
        mims_meta = mims.header["Image"]
        mims_pixel_size = mims_meta["raster"] / mims_meta["width"]
        mims_image.pixel_size_nm = mims_pixel_size
        mims_image.save()
        all_species = mims.data.species.values

        # Define the path for saving
        isotope_image_dir = os.path.join(
            os.path.dirname(mims_image.file.path),
            mims_image.file.name.split(".")[0].split("/")[-1],
            "isotopes",
        )
        if not os.path.exists(isotope_image_dir):
            os.makedirs(isotope_image_dir)
        for species in all_species:
            print(f"doing isotope {species}")
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
        if "12C" in all_species and "13C" in all_species:
            c12_im = np.asarray(Image.open(os.path.join(isotope_image_dir, "12C.png")))
            c13_im = np.asarray(Image.open(os.path.join(isotope_image_dir, "13C.png")))
            ratio = Image.fromarray(
                (np.divide(c13_im, c12_im) * 10000).astype(np.uint8)
            )
            ratio.save(os.path.join(isotope_image_dir, "13C12C_ratio.png"))
        if "15N 12C" in all_species and "14N 12C" in all_species:
            n15_im = np.asarray(
                Image.open(os.path.join(isotope_image_dir, "15N 12C.png"))
            )
            n14_im = np.asarray(
                Image.open(os.path.join(isotope_image_dir, "14N 12C.png"))
            )
            ratio = Image.fromarray(
                (np.divide(n15_im, n14_im) * 10000).astype(np.uint8)
            )
            ratio.save(os.path.join(isotope_image_dir, "15N14N_ratio.png"))
        mims_image.status = "PREPROCESSED"
        mims_image.save()

    # Now create the composite images
    isotopes = [i.name for i in mims_image_set.mims_images.first().isotopes.all()]
    if "12C" in isotopes and "13C" in isotopes:
        isotopes.append("13C12C_ratio")
    if "15N 12C" in isotopes and "14N 12C" in isotopes:
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
