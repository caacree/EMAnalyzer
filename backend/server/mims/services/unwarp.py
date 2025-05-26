import SimpleITK as sitk
from skimage.transform import SimilarityTransform, warp
from mims.model_utils import load_images_and_bboxes
from mims.services.image_utils import extract_final_digit, image_from_im_file
from mims.models import MIMSImageSet, MimsTiffImage
from mims.services.registration_utils import create_composite_mask
import os
import cv2
import sims
import tifffile
import numpy as np
from PIL import Image
import pandas as pd
from django.conf import settings

media_root = settings.MEDIA_ROOT

possible_12c_names = ["12C", "12C2"]
possible_13c_names = ["13C", "12C 13C"]
possible_15n_names = ["15N 12C", "12C 15N"]
possible_14n_names = ["14N 12C", "12C 14N"]

def command_iteration(method):
    """Callback invoked when the optimization has an iteration"""
    print(f"{method.GetOptimizerIteration():3} " + f"= {method.GetMetricValue():10.5f}")


def make_unwarp_transform(mims_image):
    reg_loc = os.path.join(media_root, mims_image.file.path[:-3])

    # Read the fixed and moving images
    fixed_image = sitk.ReadImage(
        os.path.join(reg_loc, "registration", "em_mask_for_unwarp.tiff"),
        sitk.sitkFloat32,
    )
    moving_image = sitk.ReadImage(
        os.path.join(reg_loc, "registration", "mims_mask_for_unwarp.tiff"),
        sitk.sitkFloat32,
    )

    # Set up the BSpline transformation
    transformDomainMeshSize = [8] * moving_image.GetDimension()
    tx = sitk.BSplineTransformInitializer(fixed_image, transformDomainMeshSize)

    # Set up the image registration method
    registration = sitk.ImageRegistrationMethod()
    registration.SetMetricAsMeanSquares()
    registration.SetOptimizerAsLBFGSB(
        gradientConvergenceTolerance=1e-5,
        numberOfIterations=100,
        maximumNumberOfCorrections=5,
        maximumNumberOfFunctionEvaluations=1000,
        costFunctionConvergenceFactor=1e7,
    )
    registration.SetInitialTransform(tx, True)
    registration.SetInterpolator(sitk.sitkLinear)

    registration.AddCommand(
        sitk.sitkIterationEvent, lambda: command_iteration(registration)
    )

    outTx = registration.Execute(fixed_image, moving_image)
    print("-------")
    print(outTx)
    print(
        f"Optimizer stop condition: {registration.GetOptimizerStopConditionDescription()}"
    )
    print(f" Iteration: {registration.GetOptimizerIteration()}")
    print(f" Metric value: {registration.GetMetricValue()}")

    sitk.WriteTransform(outTx, os.path.join(reg_loc, "mims_transform.tfm"))

    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(fixed_image)
    resampler.SetInterpolator(sitk.sitkLinear)
    resampler.SetDefaultPixelValue(0)
    resampler.SetTransform(outTx)

    out = resampler.Execute(moving_image)
    simg1 = sitk.Cast(sitk.RescaleIntensity(fixed_image), sitk.sitkUInt8)
    simg2 = sitk.Cast(sitk.RescaleIntensity(out), sitk.sitkUInt8)
    # cimg = sitk.Compose(simg1, simg2, simg1 // 2.0 + simg2 // 2.0)
    sitk.WriteImage(simg2, os.path.join(reg_loc, "mims_mask_unwarped.tif"))
    unwarped_composite = create_composite_mask(
        sitk.GetArrayFromImage(simg1), sitk.GetArrayFromImage(simg2)
    )
    Image.fromarray(unwarped_composite).save(
        os.path.join(reg_loc, "composite_mask_unwarped.png")
    )
    return


def make_unwarp_images(mims_image, registration_bbox=None):
    reg_loc = os.path.join(media_root, mims_image.file.path[:-3])
    tfm = os.path.join(reg_loc, "mims_transform.tfm")
    em_reference_fn = os.path.join(reg_loc, "registration", "em_mask_for_unwarp.tiff")
    mims = sims.SIMS(mims_image.file.path)
    mims_image.mims_tiff_images.all().delete()
    isotopes = list(mims_image.isotopes.all())
    for isotope in isotopes:
        img = os.path.join(reg_loc, "registration", f"{isotope.name}_warped.tiff")

        unwarped_img = unwarp_image(tfm, em_reference_fn, img)
        unwarped_img = Image.fromarray(unwarped_img)
        unwarped_img_loc = os.path.join(reg_loc, f"unwarped-{isotope.name}.png")
        unwarped_img.save(unwarped_img_loc)
        tiff_image = MimsTiffImage(
            mims_image=mims_image,
            image=unwarped_img_loc,
            name=isotope.name,
            registration_bbox=registration_bbox,
        )
        
        tiff_image.save()
        os.remove(img)
    # Create the 13C12C_ratio and 15N14N_ratio composites
    c13 = next(
        (name for name in possible_13c_names if name in isotopes),
        None,
    )
    c12 = next(
        (name for name in possible_12c_names if name in isotopes),
        None,
    )
    n15 = next(
        (name for name in possible_15n_names if name in isotopes),
        None,
    )
    n14 = next(
        (name for name in possible_14n_names if name in isotopes),
        None,
    )
    if c13 and c12:
        c13 = MimsTiffImage.objects.get(mims_image=mims_image, name=c13)
        c12 = MimsTiffImage.objects.get(mims_image=mims_image, name=c12)
        c13_img = Image.open(c13.image.path)
        c12_img = Image.open(c12.image.path)
        c13_img = c13_img.resize(c12_img.size)
        c13_img = np.array(c13_img)
        c12_img = np.array(c12_img)
        c12[c12 == 0] = 1
        species_summed = np.divide(c13, c12) * 10000
    else:
        None
def unwarp_image(tfm_file, reference_image_fn, moving_image_fn):
    tfm = sitk.ReadTransform(tfm_file)
    reference_image = sitk.ReadImage(reference_image_fn)  # , sitk.sitkUInt16)
    moving_image = sitk.ReadImage(moving_image_fn)  # , sitk.sitkUInt16)
    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(reference_image)
    resampler.SetInterpolator(sitk.sitkLinear)
    resampler.SetDefaultPixelValue(0)
    resampler.SetTransform(tfm)
    return sitk.GetArrayFromImage(resampler.Execute(moving_image))


def create_unwarped_composites(mims_imageset_id, full_em_shape):
    imageset = MIMSImageSet.objects.get(id=mims_imageset_id)
    is_complete = True
    for mims_image in imageset.mims_images.all():
        if (
            mims_image.status != "DEWARPED_ALIGNED"
            and mims_image.status != "OUTSIDE_CANVAS"
        ):
            is_complete = False
            break
    if is_complete:
        imageset.status = "ALIGNED"
        imageset.save()
        # Make the composite images
        isotopes = [i.name for i in imageset.mims_images.first().isotopes.all()]
        if "12C" in isotopes and "13C" in isotopes:
            isotopes.append("13C12C_ratio")
        if "15N 12C" in isotopes and "14N 12C" in isotopes:
            isotopes.append("15N14N_ratio")
        mims_images = sorted(
            [
                m
                for m in mims_image.image_set.mims_images.all()
                if m.status == "DEWARPED_ALIGNED"
            ],
            key=lambda m: extract_final_digit(m.file.name),
        )
        for isotope in isotopes:
            if isotope != "13C12C_ratio" and isotope != "15N14N_ratio":
                continue
            output_composites_dir = os.path.join(
                settings.MEDIA_ROOT,
                "mims_image_sets",
                str(imageset.id),
                "composites",
                "unwarped_isotopes",
            )
            os.makedirs(output_composites_dir, exist_ok=True)
            isotope_unwarped_composite = np.full(full_em_shape, 0)
            for image in mims_images:
                reg_loc = os.path.join(settings.MEDIA_ROOT, image.file.path[:-3])
                alignment = image.alignments.filter(status="FINAL_TWEAKED_ONE").first()
                alignment_padding = alignment.info["padding"]
                image_isotope = np.array(
                    Image.open(
                        os.path.join(
                            settings.MEDIA_ROOT,
                            "mims_image_sets",
                            str(image.image_set.id),
                            "mims_images",
                            str(image.file.name).split("/")[-1].split(".")[0],
                            "isotopes",
                            f"{isotope}.png",
                        )
                    )
                )

                image_isotope = np.pad(
                    image_isotope,
                    alignment_padding,
                    mode="constant",
                    constant_values=0,
                )
                # Run unwarping on JUST the padded original image, not transformed
                resampler = sitk.ResampleImageFilter()
                fixed = sitk.GetImageFromArray(np.zeros(image_isotope.shape))
                resampler.SetReferenceImage(fixed)
                resampler.SetInterpolator(sitk.sitkLinear)
                resampler.SetDefaultPixelValue(0)
                tfm = sitk.ReadTransform(os.path.join(reg_loc, "mims_transform.tfm"))
                resampler.SetTransform(tfm)
                moving = sitk.GetImageFromArray(image_isotope)
                image_isotope_unwarped = resampler.Execute(moving)
                image_isotope_unwarped = sitk.GetArrayFromImage(
                    sitk.Cast(image_isotope_unwarped, sitk.sitkUInt16)
                )

                # Once it's unwarped, then do the rotation, flipping, and scaling
                image_isotope_unwarped = Image.fromarray(image_isotope_unwarped)
                if alignment.flip_hor:
                    image_isotope_unwarped = image_isotope_unwarped.transpose(
                        Image.FLIP_LEFT_RIGHT
                    )
                image_isotope_unwarped = image_isotope_unwarped.rotate(
                    alignment.rotation_degrees, expand=True
                )
                image_isotope_unwarped = np.array(image_isotope_unwarped)

                image_isotope_unwarped = cv2.resize(
                    image_isotope_unwarped,
                    (
                        int(image_isotope_unwarped.shape[1] * alignment.scale),
                        int(image_isotope_unwarped.shape[0] * alignment.scale),
                    ),
                )
                # Check if the image exceeds the composite bounds
                canvas_insertion_area = [
                    max(alignment.y_offset, 0),
                    min(
                        alignment.y_offset + image_isotope_unwarped.shape[0],
                        isotope_unwarped_composite.shape[0],
                    ),
                    max(alignment.x_offset, 0),
                    min(
                        alignment.x_offset + image_isotope_unwarped.shape[1],
                        isotope_unwarped_composite.shape[1],
                    ),
                ]
                mims_insertion_area = [
                    max(-alignment.y_offset, 0),
                    max(-alignment.y_offset, 0)
                    + (canvas_insertion_area[1] - canvas_insertion_area[0]),
                    max(-alignment.x_offset, 0),
                    max(-alignment.x_offset, 0)
                    + (canvas_insertion_area[3] - canvas_insertion_area[2]),
                ]

                # Update only the zero locations in the composite with the values from image_isotope_unwarped
                composite_slice = isotope_unwarped_composite[
                    canvas_insertion_area[0] : canvas_insertion_area[1],
                    canvas_insertion_area[2] : canvas_insertion_area[3],
                ]
                mims_slice = image_isotope_unwarped[
                    mims_insertion_area[0] : mims_insertion_area[1],
                    mims_insertion_area[2] : mims_insertion_area[3],
                ]

                # Generate the nan mask for the composite slice
                zero_mask = composite_slice == 0

                # Update only zero locations in the composite
                composite_slice[zero_mask] = mims_slice[zero_mask]

                # Replace the region in the composite with the updated slice
                isotope_unwarped_composite[
                    canvas_insertion_area[0] : canvas_insertion_area[1],
                    canvas_insertion_area[2] : canvas_insertion_area[3],
                ] = composite_slice
            if np.max(isotope_unwarped_composite) < 256:
                isotope_unwarped_composite = isotope_unwarped_composite.astype(np.uint8)
            else:
                isotope_unwarped_composite = isotope_unwarped_composite.astype(
                    np.uint16
                )
            tifffile.imwrite(
                os.path.join(output_composites_dir, f"{isotope}.tiff"),
                isotope_unwarped_composite,
            )
