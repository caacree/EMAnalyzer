import cv2
import numpy as np
from PIL import Image
import time
import math
import os
from pathlib import Path
from scipy.spatial import ConvexHull

from mims.model_utils import get_autocontrast_image_path
from pystackreg import StackReg
from pystackreg.util import to_uint16
from scipy import ndimage


def polygon_centroid(polygon):
    try:
        poly_array = np.array(polygon, dtype=float)
        if poly_array.ndim != 2 or poly_array.shape[1] < 2:
            raise ValueError("Polygon must be an NxK array with K >= 2.")
        return np.mean(poly_array[:, :2], axis=0)
    except Exception as e:
        raise ValueError(f"Invalid data during centroid calculation: {e}")


def pts_distance(point1, point2):
    """Compute the Euclidean distance between two points."""
    return np.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)


def mask_to_polygon(mask, translate=[0, 0]):
    # Ensure the mask is of type uint8, as required by OpenCV
    mask_uint8 = mask.astype(np.uint8)

    # Find contours in the mask
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if len(contours) == 0:
        # No contours found; return empty list
        return []

    # Select the largest contour by area
    largest_contour = max(contours, key=lambda c: cv2.contourArea(c))

    # polygons = [contour.reshape(-1, 2) for contour in contours]
    polygons = [largest_contour.reshape(-1, 2)]

    # translate the polygons
    polygons = [
        [[p[0] + translate[0], p[1] + translate[1]] for p in polygon]
        for polygon in polygons
    ]

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


def get_species_summed(mims, species):
    sr = StackReg(StackReg.AFFINE)
    sr.register_stack(mims.data.loc[species].to_numpy(), reference="previous")
    stacked = sr.transform_stack(mims.data.loc[species].to_numpy())
    stacked = to_uint16(stacked)
    species_summed = stacked.sum(axis=0)
    species_summed = ndimage.median_filter(species_summed, size=1).astype(np.uint16)
    return species_summed


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


def radial_spokes(shape: np.ndarray, n_spokes: int = 6) -> np.ndarray:
    """
    Return the  `n_spokes`  vertices that lie furthest from the centroid
    in n evenly spaced angular directions (0-360°).
    """
    c = polygon_centroid(shape)
    rel = shape - c
    angles = np.linspace(0, 2 * np.pi, n_spokes, endpoint=False)
    v = np.stack([np.cos(angles), np.sin(angles)], axis=1)  # (n,2)

    # project every vertex onto each spoke direction, pick the farthest
    proj = rel @ v.T  # (Nv, n_spokes)
    idx = np.argmax(proj, axis=0)  # indices of farthest vertices
    return shape[idx]  # (n_spokes, 2)
