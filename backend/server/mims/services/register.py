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
    start_time = time.time()
    mims_image = get_object_or_404(MIMSImage, pk=mims_image_obj_id)
    mims_path = Path(mims_image.file.path)
    reg_loc = os.path.join(mims_path.parent, mims_path.stem)
    with open(os.path.join(reg_loc, "registration", "reg_shapes.json"), "r") as f:
        json_shapes = json.load(f)
    em_shapes = json_shapes["em_shapes"]
    mims_shapes = json_shapes["mims_shapes"]

    em_centroids = np.array([polygon_centroid(ep) for ep in em_shapes])
    mims_centroids = np.array([polygon_centroid(mp) for mp in mims_shapes])
    transform, flip = get_points_transform(
        mims_image.image_set, mims_centroids, em_centroids
    )
    scale = transform.scale
    rotation_radians = transform.rotation
    rotation_degrees = -np.degrees(rotation_radians)
    if rotation_degrees < 0:
        rotation_degrees += 360

    mims_image.flip = flip
    mims_image.transform = transform.params.tolist()
    mims_image.rotation_degrees = rotation_degrees
    mims_image.pixel_size_nm = (mims_image.canvas.pixel_size_nm or 5) * scale

    em_shapes_transformed = em_shapes
    mims_shapes_transformed = mims_shapes
    if flip:
        ims, bboxes = load_images_and_bboxes(mims_image.image_set, "SE", flip=True)
        max_x = np.max([pos[0] for bbox in bboxes for pos in bbox])
        mims_shapes_transformed = []
        for shape in mims_shapes:
            shape_transformed = np.array(shape).copy()
            shape_transformed[:, 0] = -shape_transformed[:, 0]  # Flip x-coordinates
            # Shift all x-coordinates to ensure they are positive
            shape_transformed[:, 0] += abs(max_x)
            mims_shapes_transformed.append(shape_transformed)
    mims_shapes_transformed = [
        transform(np.array(shape)) for shape in mims_shapes_transformed
    ]
    if shrink_em:
        em_shapes_transformed = [
            np.array(shape) / scale for shape in em_shapes_transformed
        ]
        mims_shapes_transformed = [
            np.array(shape) / scale for shape in mims_shapes_transformed
        ]

    # -----------------------------------------------------
    # Determine bounding box for the unwarping images
    # This is the rotated size of the MIMS, + int(10% of it)
    # -----------------------------------------------------\
    raw_mims = image_from_im_file(mims_image.file.path, "SE")
    rotated_dimensions = get_rotated_dimensions(
        raw_mims.shape[1], raw_mims.shape[0], transform
    )
    desired_dimensions = int(rotated_dimensions[0] * 1.1), int(
        rotated_dimensions[1] * 1.1
    )
    padding = (
        (desired_dimensions[0] - raw_mims.shape[1]) // 2,
        (desired_dimensions[1] - raw_mims.shape[0]) // 2,
    )
    raw_mims = np.pad(raw_mims, padding, mode="constant", constant_values=0)

    def bbox_to_wh(bbox_):
        return (
            max(bbox_[:, 0]) - min(bbox_[:, 0]),
            max(bbox_[:, 1]) - min(bbox_[:, 1]),
        )

    bbox = np.array([[0, 0], [512, 0], [512, 512], [0, 512]])

    transformed_bbox = None
    if flip:
        # Need to get the correct offset for the bbox once flipped, since the
        # Estimate_transform in get_points_transform uses these translated coordinates
        ims, bboxes = load_images_and_bboxes(mims_image.image_set, "SE", flip=True)
        max_x = np.max([pos[0] for bbox_ in bboxes for pos in bbox_])

        bbox_flipped = bbox.copy()
        bbox_flipped[:, 0] = -bbox_flipped[:, 0]  # x -> -x
        bbox_flipped[:, 0] += abs(max_x)

        transformed_bbox = transform(bbox_flipped)
    else:
        transformed_bbox = transform(bbox)
    ten_pct = int(bbox_to_wh(transformed_bbox)[0] * 0.1)
    extra_bbox = [
        [
            min(transformed_bbox[:, 0]) - ten_pct,
            min(transformed_bbox[:, 1]) - ten_pct,
        ],
        [
            max(transformed_bbox[:, 0]) + ten_pct,
            max(transformed_bbox[:, 1]) + ten_pct,
        ],
    ]

    mims_image.canvas_bbox = transformed_bbox.tolist()
    mims_image.save()

    if shrink_em:
        transformed_bbox = np.array(transformed_bbox) / scale
        extra_bbox = np.array(extra_bbox) / scale
    edge_size = math.ceil(
        max(extra_bbox[1][0] - extra_bbox[0][0], extra_bbox[1][1] - extra_bbox[0][1])
    )
    extra_bbox[0] = np.floor(extra_bbox[0])
    extra_bbox[1] = extra_bbox[0] + edge_size

    mims_image.registration_bbox = extra_bbox
    mims_image.save()

    min_x = extra_bbox[0][0]
    min_y = extra_bbox[0][1]

    width = int(extra_bbox[1][0] - extra_bbox[0][0])
    height = int(extra_bbox[1][1] - extra_bbox[0][1])

    # -----------------------------------------------------
    # Shift shapes so the bounding box corner is at (0,0)
    # -----------------------------------------------------
    def shift_shape(shape, x_offset, y_offset):
        return np.array([[x - x_offset, y - y_offset] for x, y in shape])

    em_shapes_shifted = [
        shift_shape(shape, min_x, min_y) for shape in em_shapes_transformed
    ]
    mims_shapes_shifted = [
        shift_shape(shape, min_x, min_y) for shape in mims_shapes_transformed
    ]

    mims_shifted_centroids = np.array(
        [polygon_centroid(mp) for mp in mims_shapes_shifted]
    )
    final_transform = get_points_transform(
        mims_image.image_set, mims_shifted_centroids, mims_centroids
    )
    print(final_transform.params)
    # -----------------------------------------------------
    # Create masks by rasterizing polygons
    # -----------------------------------------------------
    # Initialize empty masks
    em_mask = np.zeros((height, width), dtype=np.uint8)
    mims_mask = np.zeros((height, width), dtype=np.uint8)
    # Fill polygons on the mask.
    # Note: polygon() expects coordinates as (row, col), i.e. (y, x)
    # Ensure that shape coordinates are in the form (x,y), so we need [y, x]
    for shape in em_shapes_shifted:
        shape_start = time.time()
        rr, cc = polygon(shape[:, 1], shape[:, 0], (height, width))
        # Print the area and centroid of the shape
        em_mask[rr, cc] = 1
    for shape in mims_shapes_shifted:
        rr, cc = polygon(shape[:, 1], shape[:, 0], (height, width))
        mims_mask[rr, cc] = 1
    # -----------------------------------------------------
    # Save masks as TIFF images
    # -----------------------------------------------------
    em_mask_path = os.path.join(reg_loc, "em_mask_for_unwarp.tiff")
    mims_mask_path = os.path.join(reg_loc, "mims_mask_for_unwarp.tiff")

    # Convert numpy arrays to PIL images and save
    # Using "L" mode for a single-channel image (0-255)
    em_img = Image.fromarray((em_mask * 255).astype(np.uint8), mode="L")
    mims_img = Image.fromarray((mims_mask * 255).astype(np.uint8), mode="L")

    # You can use Image.save or tifffile if desired.
    em_img.save(em_mask_path, compression=None)
    mims_img.save(mims_mask_path, compression=None)

    print(f"EM mask saved to {em_mask_path}")
    print(f"MIMS mask saved to {mims_mask_path}")

    mims_image.status = "DEWARPING"
    mims_image.save()
    # make_unwarp_transform(mims_image)
    mims_image.status = "DEWARPED_ALIGNED"
    mims_image.save()
    make_unwarp_images(mims_image)


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
