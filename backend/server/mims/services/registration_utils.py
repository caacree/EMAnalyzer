import cv2
import numpy as np
from PIL import Image
import time
import os
from pathlib import Path
from scipy.spatial import ConvexHull

from mims.model_utils import get_autocontrast_image_path


def create_composite_mask(em_mask, mims_mask):
    # Ensure the masks are binary (0 and 1)
    em_mask_bin = em_mask > 0
    mims_mask_bin = mims_mask > 0

    # Create RGB channels for the masks
    height, width = em_mask.shape
    composite_image = np.zeros((height, width, 3), dtype=np.uint8)

    # Cyan (0, 255, 255) for em_mask
    composite_image[em_mask_bin] = [0, 255, 255]

    # Magenta (255, 0, 255) for mims_mask
    magenta_mask = np.zeros_like(composite_image)
    magenta_mask[mims_mask_bin] = [255, 0, 255]

    # Blend the two masks with 50% opacity
    alpha = 0.5
    composite_image = (composite_image * alpha + magenta_mask * alpha).astype(np.uint8)

    return composite_image


def find_positive_points(mask):
    """Return the coordinates of all positive points (1s) in a binary mask."""
    points = np.argwhere(mask > 0)
    return points


def compute_distance(point1, point2):
    """Compute the Euclidean distance between two points."""
    return np.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)


def furthest_distance_convex_hull(mask):
    """Find the furthest distance between any two positive points using convex hull."""
    points = find_positive_points(mask)

    if len(points) < 2:
        return 0  # No meaningful distance if fewer than 2 points

    # Find the convex hull
    hull = ConvexHull(points)
    hull_points = points[hull.vertices]

    # Compute the maximum distance between any two points on the convex hull
    max_distance = 0
    num_hull_points = len(hull_points)

    for i in range(num_hull_points):
        for j in range(i + 1, num_hull_points):
            distance = compute_distance(hull_points[i], hull_points[j])
            max_distance = max(max_distance, distance)

    return max_distance


def test_mask_iou(mask1, mask2, padding=None):
    if (
        padding is None
        or (mask1.shape[0] < mask2.shape[0])
        or (mask1.shape[1] < mask2.shape[1])
    ):
        padding = max(mask2.shape[0], mask2.shape[1])
    mask1_padded = np.pad(mask1, padding)
    _, _, _, max_loc = cv2.minMaxLoc(
        cv2.matchTemplate(mask1_padded, mask2, cv2.TM_CCOEFF_NORMED)
    )
    max_loc = (max_loc[0] - padding, max_loc[1] - padding)
    mask1_y_start = padding + max_loc[1]
    mask1_y_end = mask1_y_start + mask2.shape[0]
    mask1_x_start = padding + max_loc[0]
    mask1_x_end = mask1_x_start + mask2.shape[1]

    mask1_translated = mask1_padded[
        mask1_y_start:mask1_y_end, mask1_x_start:mask1_x_end
    ]
    return iou(mask1_translated, mask2), max_loc


def scale_between_masks(mask1, mask2, by_width=False):
    # Compute distances between corresponding points
    dist_mask1 = furthest_distance_convex_hull(mask1)
    dist_mask2 = furthest_distance_convex_hull(mask2)
    if dist_mask2:
        return dist_mask1 / dist_mask2
    return 1


def iou(mask1, mask2):
    intersection = np.logical_and(mask1, mask2)
    union = np.logical_or(mask1, mask2)
    return np.sum(intersection) / np.sum(union)


def mask_to_polygon(mask, single_polygon=True):
    # Ensure the mask is of type uint8, as required by OpenCV
    mask_uint8 = (mask * 255).astype(np.uint8)

    # Find contours in the mask
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    # Convert contours to polygons (exact boundaries)
    polygons = [contour.reshape(-1, 2) for contour in contours]
    # if single_polygon:
    #    polygons = polygons[0:1]

    return polygons


def create_mask_from_shapes(image_shape, shapes):
    """
    Create a binary mask with filled polygons.

    :param image_shape: Shape of the target image (height, width)
    :param shapes: List of polygons, each being a list of points
    :return: Binary mask with filled polygons
    """
    mask = np.zeros(image_shape, dtype=np.uint8)

    # Fill each polygon in the mask
    for shape in shapes:
        for polygon in shape:
            polygon_np = np.array(polygon, dtype=np.int32)  # Convert to int32 for cv2
            cv2.fillPoly(mask, [polygon_np], 255)  # Fill the polygon with white (255)

    return mask


def create_registration_images(mims_image, masks=None):
    stime = time.time()
    print("creating registration images", time.time() - stime)
    em_image_obj = Image.open(mims_image.image_set.canvas.images.first().file.path)
    mims_path = Path(mims_image.file.path)
    save_reg_loc = os.path.join(mims_path.parent, mims_path.stem, "registration")
    if not os.path.exists(save_reg_loc):
        os.makedirs(save_reg_loc)

    alignment = mims_image.alignments.filter(status="FINAL_TWEAKED_ONE").first()
    if not alignment:
        alignment = mims_image.alignments.filter(status="USER_ROUGH_ALIGNMENT").first()
    if not alignment:
        raise Exception("No valid alignment to use to create the images")
    scale = alignment.scale

    # Calculate the region of the transformed EM image that corresponds to the MIMS image
    mims_image_obj = Image.open(get_autocontrast_image_path(mims_image, "SE"))
    mims_image_obj = mims_image_obj.rotate(-alignment.rotation_degrees, expand=True)
    extra = int(100 * scale)
    em_y_start = max(alignment.y_offset - extra, 0)
    em_y_end = int(
        min(em_y_start + mims_image_obj.height * scale + extra, em_image_obj.height)
    )
    em_x_start = max(alignment.x_offset - extra, 0)
    em_x_end = int(
        min(em_x_start + mims_image_obj.width * scale + extra, em_image_obj.width)
    )
    em_image_obj = Image.fromarray(
        np.array(em_image_obj)[em_y_start:em_y_end, em_x_start:em_x_end]
    )
    # Scale down the EM image (inverse of scaling up MIMS)
    em_image_transformed = em_image_obj.resize(
        (
            int(em_image_obj.width / scale),
            int(em_image_obj.height / scale),
        ),
    )

    # Transform the EM image instead of the MIMS images
    if alignment.flip_hor:
        em_image_transformed = em_image_transformed.transpose(Image.FLIP_LEFT_RIGHT)
    em_image_transformed = em_image_transformed.rotate(
        alignment.rotation_degrees, expand=True
    )

    em_image_transformed = np.array(em_image_transformed)
    Image.fromarray(em_image_transformed).save(
        os.path.join(save_reg_loc, f"em{'_final' if masks else ''}.png")
    )
