import json
import math
import time
from django.shortcuts import get_object_or_404
from mims.services.image_utils import image_from_im_file
from mims.services.orient_images import get_points_transform
from mims.services.registration_utils import (
    create_composite_mask,
    scale_between_masks,
    test_mask_iou,
)
import tifffile
from skimage.transform import estimate_transform, SimilarityTransform
from skimage.draw import polygon
from skimage.transform import warp
from mims.model_utils import (
    get_autocontrast_image_path,
    load_images_and_bboxes,
)
from mims.models import MIMSImage
import os
from pathlib import Path
import cv2
from PIL import Image
from mims.services.registration_utils import get_rotated_dimensions
import numpy as np
from mims.services.unwarp import make_unwarp_transform, make_unwarp_images

MASK_PADDING = 20

from .register3 import register_images3_test
from .register2 import register_images2_test


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


def polygon_centroid(polygon):
    """
    Compute the centroid of a polygon given by an Nx2 array of coordinates.
    """
    return np.mean(np.array(polygon), axis=0)[0:2]


def register_images(mims_image_obj_id, shrink_em=False):
    register_images2_test(mims_image_obj_id, shrink_em)
    # register_images3_test(mims_image_obj_id, shrink_em)


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
