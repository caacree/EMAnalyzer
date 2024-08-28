import os
from datetime import datetime
import numpy as np
import pyvips
import sims
from django.conf import settings

from .image_utils import (
    manipulate_image,
    update_top_locations,
    do_sliding_search,
    correct_inner_zeros,
)


def threshold_match(
    im1_full, im2_full, THRESHOLD_8BIT_BUFFER=10, angle=None, flip_hor=None
):
    valid_im1 = im1_full > 0
    valid_im2 = im2_full > 0
    im1_threshold = np.percentile(im1_full, 90) - THRESHOLD_8BIT_BUFFER
    im1 = np.where(im1_full > im1_threshold, 255, 0).astype(np.uint8)
    im2_threshold = np.percentile(im2_full, 90) - THRESHOLD_8BIT_BUFFER
    im2 = np.where(im2_full > im2_threshold, 255, 0).astype(np.uint8)

    best_overall_locations = []

    if angle is not None and flip_hor is not None:
        im2_manipulated = manipulate_image(im2, angle, flip_hor)
        best_overall_locations = [
            (i, (angle, flip_hor))
            for i in do_sliding_search(
                im1, im2_manipulated, valid_im1, valid_im2, angle, flip_hor
            )
        ]
    else:
        for test_angle in range(0, 360, 15):
            if test_angle in [0, 90, 180, 270]:
                print(
                    datetime.now(), "starting angle", test_angle, best_overall_locations
                )
            for test_flip_hor in [True, False]:
                im2_manipulated = manipulate_image(im2, test_angle, test_flip_hor)
                valid_im2 = im2_manipulated > 0
                im2_manipulated = np.where(
                    im2_manipulated > im2_threshold, 255, 0
                ).astype(np.uint8)
                best_for_iteration = do_sliding_search(
                    im1,
                    im2_manipulated,
                    valid_im1,
                    valid_im2,
                    test_angle,
                    test_flip_hor,
                )
                for top_for_iteration in best_for_iteration:
                    best_overall_locations = update_top_locations(
                        best_overall_locations,
                        top_for_iteration[0],
                        top_for_iteration[1],
                        top_for_iteration[2],
                        top_for_iteration[3],
                        top_for_iteration[4],
                    )

    return best_overall_locations


def create_alignment_estimates(mims_image, confirmed_alignment=None):
    print(
        f"{datetime.now()} starting alignment. Confirmed alignment is {confirmed_alignment}"
    )
    if confirmed_alignment:
        # Get the em coordinates of the mims_image given the confirmed one.
        print(
            f"Found confirmed alignment in project: angle of {confirmed_alignment.rotation_degrees}, flip_hor of {confirmed_alignment.flip_hor}"
        )
        confirmed_im_obj = sims.SIMS(confirmed_alignment.mims_image.file)
        current_im_obj = sims.SIMS(mims_image.mims_image.file)
        current_im_x = current_im_obj.header["sample x"]
        current_im_y = current_im_obj.header["sample y"]
        confirmed_im_obj_x = confirmed_im_obj.header["sample x"]
        confirmed_im_obj_y = confirmed_im_obj.header["sample y"]
        confirmed_alignment_em_x = confirmed_alignment.x_offset
        confirmed_alignment_em_y = confirmed_alignment.y_offset
        scale = confirmed_alignment.scale
        mims_pixel_size = mims_image.pixel_size_nm
        em_pixel_size = mims_image.image_set.em_image.pixel_size_nm
        angle = confirmed_alignment.rotation_degrees
        flip_hor = confirmed_alignment.flip_hor
        # Calculate the difference in microns between the current and confirmed nanoSIMS images
        delta_x_microns = current_im_x - confirmed_im_obj_x
        delta_y_microns = current_im_y - confirmed_im_obj_y

        # Convert the difference to EM pixels
        delta_x_em_pixels = delta_x_microns * 1000 / em_pixel_size
        delta_y_em_pixels = delta_y_microns * 1000 / em_pixel_size

        # Create rotation matrix
        theta = np.radians(angle)
        rotation_matrix = np.array(
            [[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]]
        )
        # Apply rotation to the delta coordinates
        rotated_delta = np.dot(
            rotation_matrix, np.array([delta_x_em_pixels, delta_y_em_pixels])
        )

        # Apply flip_hor if necessary
        if flip_hor:
            rotated_delta[0] = -rotated_delta[0]
        # Calculate the new EM coordinates
        new_em_x = confirmed_alignment_em_x + rotated_delta[0]
        new_em_y = confirmed_alignment_em_y + rotated_delta[1]

        # Apply scale factor
        new_em_x *= scale
        new_em_y *= scale

        # Round to nearest integer (assuming EM coordinates are in pixels)
        new_em_x = round(new_em_x)
        new_em_y = round(new_em_y)

        print(mims_image.file.filename)
        print(
            confirmed_im_obj_x,
            confirmed_im_obj_y,
            confirmed_alignment_em_x,
            confirmed_alignment_em_y,
        )
        print(new_em_x, new_em_y)
        mims_image.alignments.filter(status="FROM_SET").delete()
        """new_from_set_alignment = MIMSAlignment(
            mims_image=mims_image,
            status="FROM_SET",
            x_offset=new_em_x,
            y_offset=new_em_y,
            rotation_degrees=confirmed_alignment.rotation_degrees,
            flip_hor=confirmed_alignment.flip_hor,
            scale=confirmed_alignment.scale,
        )
        new_from_set_alignment.save()"""
        return

    # Clear old alignments
    if hasattr(mims_image, "alignments") and mims_image.alignments.exists():
        mims_image.alignments.all().delete()

    # Get scale
    mims_pixel_size = mims_image.pixel_size_nm
    em_pixel_size = mims_image.image_set.em_image.pixel_size_nm
    scale = em_pixel_size / mims_pixel_size

    # Load the 32S image
    sulfur_image_path = os.path.join(
        settings.MEDIA_ROOT,
        "mims_images",
        str(mims_image.image_set.id),
        str(mims_image.id),
        "isotopes",
        "32S_autocontrast.png",
    )
    sulfur_image = pyvips.Image.new_from_file(sulfur_image_path).numpy()

    # Prep the 32S image:
    # Invert the 8-bit image
    sulfur_image = np.invert(sulfur_image)
    # Change 0 to 1 so we can ignore extra pixels from rotation
    sulfur_image = np.where(sulfur_image == 0, 1, sulfur_image)

    # Load and scale the em image
    em_image_path = mims_image.image_set.em_image.file.path
    em_image = pyvips.Image.new_from_file(em_image_path).resize(scale).numpy()

    # Set inner 0s to 1s so we can expand with more 0s
    em_image = correct_inner_zeros(em_image).astype(np.uint8)
    # Expand the image to include padding for the sliding check
    EM_PADDING = int(sulfur_image.shape[0] * 0.6)
    em_image = (
        pyvips.Image.new_from_array(em_image)
        .embed(
            EM_PADDING,
            EM_PADDING,
            em_image.shape[1] + 2 * EM_PADDING,
            em_image.shape[0] + 2 * EM_PADDING,
            background=0,
        )
        .numpy()
    )
    print(datetime.now(), "starting threshold match")
    best_matches = threshold_match(em_image, sulfur_image, 10, angle, flip_hor)
    print(datetime.now(), best_matches)
    alignment_status = (
        "ESTIMATE_INITIAL"
        if angle is None and flip_hor is None
        else "ESTIMATE_FROM_SET"
    )
    for match in best_matches:
        # Correct for the padding and scaling
        actual_x = (match[0] - EM_PADDING) / scale
        actual_y = (match[1] - EM_PADDING) / scale
        print(
            "FINAL", EM_PADDING, match, actual_x, actual_y, match[2], match[3], match[4]
        )
        alignment = MIMSAlignment(
            mims_image=mims_image,
            x_offset=actual_x,
            y_offset=actual_y,
            rotation_degrees=match[3],
            flip_hor=match[4],
            scale=scale,
            status=alignment_status,
        )
        alignment.save()
