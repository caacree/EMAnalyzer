import json
import time
from django.shortcuts import get_object_or_404
from mims.services.unwarp import create_unwarped_composites
from mims.services.orient_images import get_points_transform, largest_inner_square
from mims.services.registration_utils import (
    create_composite_mask,
    create_mask_from_shapes,
    scale_between_masks,
    test_mask_iou,
)
from shapely.geometry import Polygon
from rasterio.features import rasterize
from rasterio.transform import Affine
from skimage.draw import polygon
from mims.model_utils import (
    get_autocontrast_image_path,
    load_images_and_bboxes,
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


def polygon_centroid(polygon):
    """
    Compute the centroid of a polygon given by an Nx2 array of coordinates.
    """
    return np.mean(np.array(polygon), axis=0)[0:2]


def register_images(mims_image_obj_id):
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
    mims_image.rotation_degrees = rotation_degrees
    mims_image.pixel_size_nm = (mims_image.canvas.pixel_size_nm or 5) * scale
    bbox = np.array([[0, 0], [512, 0], [512, 512], [0, 512]])

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

    mims_image.canvas_bbox = transformed_bbox.tolist()
    mims_image.save()

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

    # -----------------------------------------------------
    # Determine bounding box for the unwarping images, use 1000px padding on the EM bounds of the MIMS image
    # -----------------------------------------------------
    padding = 1000
    em_bbox = np.array(
        [
            [
                int(min(c[0] for c in mims_image.canvas_bbox) - padding),
                int(min(c[1] for c in mims_image.canvas_bbox) - padding),
            ],
            [
                int(max(c[0] for c in mims_image.canvas_bbox) + padding),
                int(max(c[1] for c in mims_image.canvas_bbox) + padding),
            ],
        ]
    )

    min_x = em_bbox[0][0]
    min_y = em_bbox[0][1]

    width = em_bbox[1][0] - em_bbox[0][0]
    height = em_bbox[1][1] - em_bbox[0][1]
    print(f"min_x: {min_x}, min_y: {min_y}, width: {width}, height: {height}")

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

    print("starting unwarping")
    mims_image.status = "DEWARPING"
    mims_image.save()
    unwarp_image(mims_image)
    mims_image.status = "DEWARPED_ALIGNED"
    mims_image.save()
    print("done unwarping")
    # Check if the imageset is complete
    # create_unwarped_composites(mims_image.image_set.id, full_em_shape=full_em.shape)
    # print("done creating unwarped composites")


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
