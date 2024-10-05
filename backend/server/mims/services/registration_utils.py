import cv2
import numpy as np
from PIL import Image
import time
import os
from pathlib import Path
from scipy.spatial import ConvexHull

from mims.services.concat_utils import get_autocontrast_image_path

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

def test_mask_iou(mask1, mask2):
    padding = int(max(mask1.shape[0], mask1.shape[1]) * 0.5)
    mask1_padded = np.pad(mask1, padding)
    _, _, _, max_loc = cv2.minMaxLoc(
        cv2.matchTemplate(mask1_padded, mask2, cv2.TM_CCOEFF_NORMED)
    )
    max_loc = (max_loc[0] - padding, max_loc[1] - padding)
    mask1_y_start = padding + max_loc[1]
    mask1_y_end = mask1_y_start + mask2.shape[0]
    mask1_x_start = padding + max_loc[0]
    mask1_x_end = mask1_x_start + mask2.shape[1]

    mask1_translated = mask1_padded[mask1_y_start:mask1_y_end, mask1_x_start:mask1_x_end]
    return iou(mask1_translated, mask2), max_loc

def scale_between_masks(mask1, mask2, by_width=False):
    # Compute distances between corresponding points
    dist_mask1 = furthest_distance_convex_hull(mask1)
    dist_mask2 = furthest_distance_convex_hull(mask2)
    return dist_mask1 / dist_mask2

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
    #if single_polygon:
    #    polygons = polygons[0:1]

    return polygons


def create_registration_images(mims_image, masks=None):
    stime = time.time()
    print("creating registration images", time.time() - stime)
    em_image_obj = np.array(
        Image.open(mims_image.image_set.canvas.images.first().file.path)
    )
    mims_path = Path(mims_image.file.path)
    save_reg_loc = os.path.join(mims_path.parent, mims_path.stem, "registration")
    if not os.path.exists(save_reg_loc):
        os.makedirs(save_reg_loc)
    # Create the cropped EM image for registration
    # as well as the scaled up, translated MIMS image
    #alignment = mims_image.alignments.filter(
    #    status="USER_ROUGH_ALIGNMENT"
    #).first()
    alignment = mims_image.alignments.filter(status="FINAL_TWEAKED_ONE").first()
    if not alignment:
        alignment = mims_image.alignments.first()
    scale = alignment.scale
    em_cropped = None

    for isotope in mims_image.isotopes.all():
        print(f"isotope {isotope} starting at {time.time() - stime}")
        mims_image_obj = Image.open(get_autocontrast_image_path(mims_image, isotope))
        mims_image_obj = mims_image_obj.rotate(-alignment.rotation_degrees, expand=True)
        if alignment.flip_hor:
            mims_image_obj = mims_image_obj.transpose(Image.FLIP_LEFT_RIGHT)
        mims_image_obj = np.array(mims_image_obj)
        mims_image_obj = cv2.resize(
            mims_image_obj,
            (
                int(mims_image_obj.shape[1] * scale),
                int(mims_image_obj.shape[0] * scale),
            ),
        )
        if em_cropped is None:
            mims_shape = mims_image_obj.shape
            em_cropped = em_image_obj[
                max(alignment.y_offset, 0) : min(
                    alignment.y_offset + int(mims_shape[0]), em_image_obj.shape[0]
                ),
                max(alignment.x_offset, 0) : min(
                    alignment.x_offset + int(mims_shape[1]), em_image_obj.shape[1]
                ),
            ]
            Image.fromarray(em_cropped).save(os.path.join(save_reg_loc, f"em{"_final" if masks else ""}.png"))
        mims_image_obj = Image.fromarray(mims_image_obj)
        mims_image_obj.save(os.path.join(save_reg_loc, f"{isotope}{"_final" if masks else ""}.png"))
    if masks:
        mims_image_obj = np.array(mims_image_obj)
        mims_y_start = max(-alignment.y_offset, 0)
        mims_y_end = min(
            mims_y_start + em_cropped.shape[0], mims_image_obj.shape[0]
        )
        mims_x_start = max(-alignment.x_offset, 0)
        mims_x_end = min(
            mims_x_start + em_cropped.shape[1], mims_image_obj.shape[1]
        )
        mims_image_obj = mims_image_obj[
            mims_y_start:mims_y_end, mims_x_start:mims_x_end
        ]
        em_mask = masks["em_mask"][: em_cropped.shape[0], : em_cropped.shape[1]]
        mims_mask = masks[f"mims_mask"][
            : em_cropped.shape[0], : em_cropped.shape[1]
        ]
        Image.fromarray(em_mask).save(
            os.path.join(save_reg_loc, "em_reg_mask.tiff")
        )
        Image.fromarray(mims_mask).save(
            os.path.join(save_reg_loc, "mims_reg_mask.tiff")
        )
        composite_final = create_composite_mask(em_mask, mims_mask)
        print("composite_final", composite_final.shape)
        Image.fromarray(composite_final).save(
            os.path.join(save_reg_loc, "composite_mask_final.png")
        )


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
