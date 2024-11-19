import json
from django.shortcuts import get_object_or_404
from mims.services.unwarp import create_unwarped_composites
from mims.services.orient_images import largest_inner_square
from mims.services.registration_utils import (
    create_composite_mask,
    create_mask_from_shapes,
    scale_between_masks,
    test_mask_iou,
)
from mims.model_utils import (
    get_autocontrast_image_path,
    get_concatenated_image,
)
from mims.models import Isotope, MIMSAlignment, MIMSImage
import os
from pathlib import Path
import cv2
from PIL import Image
import numpy as np
from mims.services import unwarp_image

MASK_PADDING = 20


def match_masks(em_mask, mims_mask, reg_loc):
    scale_diff = 1
    orig_iou, orig_translation = test_mask_iou(em_mask, mims_mask)

    # Make an image with both masks, where one set is
    # first test the scale if needed: take furthest points and calculate distances
    # Get bounding box of 1s for each mask
    furthest_points_scale = scale_between_masks(em_mask, mims_mask)
    print("Furthest points scale test", furthest_points_scale)
    # Scale the em mask and test the iou
    em_mask_test = cv2.resize(
        em_mask,
        (
            int(em_mask.shape[1] / furthest_points_scale),
            int(em_mask.shape[0] / furthest_points_scale),
        ),
    )
    scaled_iou, scaled_translation = test_mask_iou(em_mask_test, mims_mask)

    em_to_use = em_mask
    translation_to_use = orig_translation
    if scaled_iou > orig_iou:
        print("scaled is better")
        em_to_use = em_mask_test
        translation_to_use = scaled_translation
        scale_diff *= furthest_points_scale

    em_to_use = np.array(em_to_use)
    # Pad the em if translation means it exceeds the bounds
    lpad = max(0, -translation_to_use[0])
    rpad = max(0, translation_to_use[0] + mims_mask.shape[1] - em_to_use.shape[1])
    tpad = max(0, -translation_to_use[1])
    bpad = max(0, translation_to_use[1] + mims_mask.shape[0] - em_to_use.shape[0])
    em_to_use = np.pad(em_to_use, ((tpad, bpad), (lpad, rpad)))
    em_to_use = em_to_use[
        max(0, translation_to_use[1]) : mims_mask.shape[0]
        + max(0, translation_to_use[1]),
        max(0, translation_to_use[0]) : mims_mask.shape[1]
        + max(0, translation_to_use[0]),
    ]
    # Pad both 20px so the dewarping can be done without worrying about the edges
    em_to_use = np.pad(em_to_use, MASK_PADDING, mode="constant", constant_values=0)
    mims_mask_padded = np.pad(
        mims_mask, MASK_PADDING, mode="constant", constant_values=0
    )

    # Translate the em mask to match the mims mask
    composite_mask = create_composite_mask(em_to_use, mims_mask_padded)
    Image.fromarray(em_to_use).save(os.path.join(reg_loc, "em_mask_for_unwarp.tiff"))
    Image.fromarray(mims_mask_padded).save(
        os.path.join(reg_loc, "mims_mask_for_unwarp.tiff")
    )
    Image.fromarray(composite_mask).save(
        os.path.join(reg_loc, "composite_mask_translated.png")
    )

    return (scale_diff, translation_to_use)


def register_images(mims_image_obj_id):
    mims_image = get_object_or_404(MIMSImage, pk=mims_image_obj_id)
    mims_path = Path(mims_image.file.path)
    print(f"Registering images for {mims_image}")
    reg_loc = os.path.join(mims_path.parent, mims_path.stem)
    with open(os.path.join(reg_loc, "registration", "reg_shapes.json"), "r") as f:
        json_shapes = json.load(f)
    em_shapes = json_shapes["em_shapes"]
    mims_shapes = json_shapes["mims_shapes"]

    # Update the alignment in the database
    old_alignment = mims_image.alignments.filter(status="USER_ROUGH_ALIGNMENT").first()

    # Load the original images
    mims_path = Path(mims_image.file.path)
    reg_loc = os.path.join(mims_path.parent, mims_path.stem)
    em_img = np.array(Image.open(os.path.join(reg_loc, "registration", "em.png")))
    mims_img = np.array(Image.open(os.path.join(reg_loc, "isotopes", "32S.png")))

    # Create binary masks from polygons
    em_mask_orig = create_mask_from_shapes(em_img.shape[:2], em_shapes)
    mims_mask = create_mask_from_shapes(mims_img.shape[:2], mims_shapes)
    new_scale, new_translation = match_masks(em_mask_orig, mims_mask, reg_loc)
    print("new stuff:", new_scale, new_translation)
    updated_scale = new_scale * old_alignment.scale
    # Refind the translated EM we're using - easier than trying to
    # back-calculate it
    if new_scale:
        em_img = cv2.resize(
            em_img,
            (
                int(em_img.shape[1] / new_scale),
                int(em_img.shape[0] / new_scale),
            ),
        )
    lpad = max(0, -new_translation[0])
    rpad = max(0, new_translation[0] + mims_mask.shape[1] - em_img.shape[1])
    tpad = max(0, -new_translation[1])
    bpad = max(0, new_translation[1] + mims_mask.shape[0] - em_img.shape[0])
    em_img = np.pad(em_img, ((tpad, bpad), (lpad, rpad)))
    em_img = em_img[
        max(0, new_translation[1]) : mims_mask.shape[0] + max(0, new_translation[1]),
        max(0, new_translation[0]) : mims_mask.shape[1] + max(0, new_translation[0]),
    ]

    em_img = Image.fromarray(em_img)
    # Then do the transformations to it
    em_img = em_img.rotate(-old_alignment.rotation_degrees, expand=True)
    if old_alignment.flip_hor:
        em_img = em_img.transpose(Image.FLIP_LEFT_RIGHT)
    # Scale it up
    em_img = Image.fromarray(
        cv2.resize(
            np.array(em_img),
            (int(em_img.width * updated_scale), int(em_img.height * updated_scale)),
        )
    )
    em_img.save(os.path.join(reg_loc, "em_cropped2.png"))
    # Calculate the cropping box
    largest_inner_square_side = int(
        largest_inner_square(em_img.width, old_alignment.rotation_degrees)
    )
    center_x, center_y = em_img.width // 2, em_img.height // 2
    start_x = center_x - largest_inner_square_side // 2
    start_y = center_y - largest_inner_square_side // 2
    end_x = center_x + largest_inner_square_side // 2
    end_y = center_y + largest_inner_square_side // 2
    amount_to_adjust = (em_img.height - (end_y - start_y)) // 2
    em_to_find = Image.fromarray(np.array(em_img)[start_y:end_y, start_x:end_x])

    full_em = np.array(Image.open(mims_image.image_set.canvas.images.first().file.path))

    search_buffer = int(mims_mask.shape[0] * updated_scale * 0.3)
    em_search_coords = [
        old_alignment.y_offset - search_buffer,
        old_alignment.y_offset
        + int(mims_mask.shape[0] * updated_scale)
        + search_buffer * 2,
        old_alignment.x_offset - search_buffer,
        old_alignment.x_offset
        + int(mims_mask.shape[1] * updated_scale)
        + search_buffer * 2,
    ]
    lpad = max(0, -em_search_coords[2])
    rpad = max(0, em_search_coords[3] - full_em.shape[1])
    tpad = max(0, -em_search_coords[0])
    bpad = max(0, em_search_coords[1] - full_em.shape[0])
    search_padding = ((tpad, bpad), (lpad, rpad))
    em_to_search = np.pad(full_em, search_padding)
    em_to_search = em_to_search[
        em_search_coords[0] + tpad : em_search_coords[1] + tpad,
        em_search_coords[2] + lpad : em_search_coords[3] + lpad,
    ]
    Image.fromarray(em_to_search).save(os.path.join(reg_loc, "em_to_search.png"))
    # match template
    em_to_search = np.array(em_to_search)
    result = cv2.matchTemplate(
        em_to_search, np.asarray(em_to_find), cv2.TM_CCOEFF_NORMED
    )
    _, _, _, max_loc = cv2.minMaxLoc(result)
    # Adjust back from the box search thing
    max_loc = [r - amount_to_adjust for r in max_loc]
    new_x_offset = em_search_coords[2] + max_loc[0] - int(MASK_PADDING * updated_scale)
    new_y_offset = em_search_coords[0] + max_loc[1] - int(MASK_PADDING * updated_scale)

    # Save the new alignment
    mims_image.alignments.filter(status="FINAL_TWEAKED_ONE").delete()
    alignment = MIMSAlignment.objects.create(
        mims_image=mims_image,
        x_offset=new_x_offset,
        y_offset=new_y_offset,
        rotation_degrees=old_alignment.rotation_degrees,
        flip_hor=old_alignment.flip_hor,
        scale=updated_scale,
        status="FINAL_TWEAKED_ONE",
        info={
            "padding": MASK_PADDING,
        },
    )
    alignment.save()
    print("starting unwarping")
    mims_image.status = "DEWARPING"
    mims_image.save()
    unwarp_image(mims_image)
    mims_image.status = "DEWARPED_ALIGNED"
    mims_image.save()
    print("done unwarping")
    # Check if the imageset is complete
    create_unwarped_composites(mims_image.image_set.id, full_em_shape=full_em.shape)
    print("done creating unwarped composites")


def get_images_from_alignment(mims_img_obj, full_em):
    mims_image = get_object_or_404(MIMSImage, pk=mims_img_obj)
    mims_path = Path(mims_image.file.path)
    alignment = mims_image.alignments.filter(status="FINAL_TWEAKED_ONE").first()
    reg_loc = os.path.join(mims_path.parent, mims_path.stem)

    # test if the em_image and mims_image can be re-calculated from the available info
    mims = np.array(Image.open(get_autocontrast_image_path(mims_image, "SE")))
    mims = np.pad(mims, alignment.info["padding"], mode="constant", constant_values=0)
    mims = Image.fromarray(mims)
    if alignment.flip_hor:
        mims = mims.transpose(Image.FLIP_LEFT_RIGHT)
    mims = mims.rotate(alignment.rotation_degrees, expand=True)
    mims = mims.resize(
        (int(mims.width * alignment.scale), int(mims.height * alignment.scale)),
    )
    mims = np.array(mims)
    Image.fromarray(mims).save(os.path.join(reg_loc, "mims_cropped.png"))

    tpad = max(0, -alignment.y_offset)
    bpad = max(0, alignment.y_offset + mims.shape[0] - full_em.shape[0])
    lpad = max(0, -alignment.x_offset)
    rpad = max(0, alignment.x_offset + mims.shape[1] - full_em.shape[1])
    full_em = np.pad(full_em, ((tpad, bpad), (lpad, rpad)))
    Image.fromarray(
        full_em[
            max(0, alignment.y_offset) : max(0, alignment.y_offset) + mims.shape[0],
            max(0, alignment.x_offset) : max(0, alignment.x_offset) + mims.shape[1],
        ]
    ).save(os.path.join(reg_loc, "em_cropped.png"))
    return
