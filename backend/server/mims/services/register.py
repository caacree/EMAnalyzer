import json
import math
import time
from django.shortcuts import get_object_or_404

# Assume these are correctly implemented and imported
# from mims.services.image_utils import image_from_im_file
# from mims.services.orient_images import get_points_transform
import tifffile
from mims.services.image_utils import image_from_im_file
from mims.services.orient_images import get_points_transform
from mims.models import MIMSImage
import os
from pathlib import Path
import numpy as np
from scipy.interpolate import griddata
from skimage.transform import ThinPlateSplineTransform, warp
import numpy as np
import math
import cv2
import os
from pathlib import Path
from mims.services.registration_utils import (
    polygon_centroid,
    image_from_im_file,
    get_points_transform,
)
from django.shortcuts import get_object_or_404
from mims.models import MIMSImage
import time


# --- Helper Functions ---
def polygon_centroid(polygon):
    try:
        poly_array = np.array(polygon, dtype=float)
        if poly_array.ndim != 2 or poly_array.shape[1] < 2:
            raise ValueError("Polygon must be an NxK array with K >= 2.")
        return np.mean(poly_array[:, :2], axis=0)
    except Exception as e:
        raise ValueError(f"Invalid data during centroid calculation: {e}")


def load_shapes(path):
    # --- Load Shapes ---
    shapes_json_path = Path(path)
    json_shapes = None
    if not shapes_json_path.exists():
        raise FileNotFoundError(f"Shape file not found: {shapes_json_path}")
    try:
        with open(shapes_json_path, "r") as f:
            json_shapes = json.load(f)
    except Exception as e:
        raise IOError(f"Error reading/parsing {shapes_json_path}: {e}") from e
    return json_shapes


def get_centroids_from_json(json_shapes):
    try:
        shapes = [np.array(s, dtype=float) for s in json_shapes]
        shapes = [
            s for s in shapes if s.ndim == 2 and s.shape[0] >= 3 and s.shape[1] >= 2
        ]
        centroids = np.array([polygon_centroid(ep) for ep in shapes])
        return centroids
    except Exception as e:
        raise ValueError(f"Error processing shapes/centroids: {e}") from e


def load_mims_data(mims_image):
    """Load MIMS data from the image file."""
    all_isotope_data = []
    isotope_names = []  # Keep track of names in order
    isotopes_to_process = list(mims_image.isotopes.all())
    h_mims, w_mims = None, None  # Initialize dimensions

    for isotope in isotopes_to_process:
        img_mims = image_from_im_file(
            mims_image.file.path, isotope.name, autocontrast=False
        )
        if img_mims is None:
            print(f"Warning: Failed to load MIMS image for {isotope.name}. Skipping.")
            continue
        if h_mims is None:  # Get dimensions from the first successfully loaded image
            h_mims, w_mims = img_mims.shape
            print(f"Base MIMS shape from {isotope.name}: {(h_mims, w_mims)}")
        elif img_mims.shape != (h_mims, w_mims):  # Check consistency
            print(
                f"Warning: Isotope {isotope.name} shape {img_mims.shape} differs from base {(h_mims, w_mims)}. Skipping."
            )
            continue

        all_isotope_data.append(img_mims)
        isotope_names.append(isotope.name)

    if h_mims is None:  # Check if any image was loaded successfully
        raise ValueError(
            "Failed to load any isotope image or determine base dimensions."
        )

    # Stack into a 3D array
    try:
        mims_data_cube = np.stack(all_isotope_data, axis=0)
        print(f"Loaded data cube shape: {mims_data_cube.shape}")
        del all_isotope_data  # Free memory
    except ValueError as e:
        raise ValueError(
            f"Could not stack isotope images, likely inconsistent shapes: {e}"
        )
    return isotope_names, (h_mims, w_mims), mims_data_cube


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


def validate_mims_image(mims_image_id):
    try:
        mims_image = get_object_or_404(MIMSImage, pk=mims_image_id)
    except Exception as e:
        raise ValueError(f"Could not find MIMSImage ID {mims_image_id}: {e}") from e

    if (
        not mims_image.file
        or not hasattr(mims_image.file, "path")
        or not mims_image.file.path
    ):
        raise ValueError(f"MIMSImage {mims_image_id} lacks a valid file path.")
    mims_path = Path(mims_image.file.path)
    if not mims_path.exists():
        raise FileNotFoundError(f"MIMS file not found: {mims_path}")

    reg_loc = mims_path.parent / mims_path.stem / "registration"
    os.makedirs(reg_loc, exist_ok=True)

    json_shapes = load_shapes(reg_loc / "reg_shapes.json")
    em_shapes = [np.array(s, dtype=float) for s in json_shapes.get("em_shapes", [])]
    mims_shapes = [np.array(s, dtype=float) for s in json_shapes.get("mims_shapes", [])]
    em_pts = [np.array(s, dtype=float) for s in json_shapes.get("em_pts", [])]
    mims_pts = [np.array(s, dtype=float) for s in json_shapes.get("mims_pts", [])]
    em_shapes = [
        s for s in em_shapes if s.ndim == 2 and s.shape[0] >= 3 and s.shape[1] >= 2
    ]
    mims_shapes = [
        s for s in mims_shapes if s.ndim == 2 and s.shape[0] >= 3 and s.shape[1] >= 2
    ]
    if not mims_shapes or not em_shapes:
        raise ValueError("No valid MIMS or EM shapes found.")
    if len(mims_shapes) != len(em_shapes):
        raise ValueError("MIMS and EM shape lists differ in length.")
    return (mims_image, em_shapes, mims_shapes, em_pts, mims_pts)


def get_mims_dims(mims_image):
    isotope = mims_image.isotopes.first()
    img_mims = image_from_im_file(
        mims_image.file.path, isotope.name, autocontrast=False
    )
    return img_mims.shape


def register_images(mims_image_obj_id):
    start_time = time.time()

    # --- Get MIMS Object and Paths ---
    mims_image, em_shapes, mims_shapes, em_pts, mims_pts = validate_mims_image(
        mims_image_obj_id
    )

    em_centroids = np.array([polygon_centroid(ep) for ep in em_shapes])
    mims_centroids = np.array([polygon_centroid(mp) for mp in mims_shapes])
    em_centroids.extend(em_pts)
    mims_centroids.extend(mims_pts)

    # --- Get Initial Transform ---
    image_view_set = mims_image.image_set

    selected_tform, needs_flip, _ = get_points_transform(
        image_view_set, mims_centroids, em_centroids
    )
    h_mims, w_mims = get_mims_dims(mims_image)

    # Do the flip transformation if needed
    mims_image.flip = needs_flip
    mims_image.save(update_fields=["flip"])
    if needs_flip:
        mims_shapes_flipped = []
        for mims_shape in mims_shapes:
            mims_shapes_flipped.append(
                [[(w_mims - 1) - pt[0], pt[1]] for pt in mims_shape]
            )
        mims_shapes = mims_shapes_flipped
        mims_pts = [[(w_mims - 1) - pt[0], pt[1]] for pt in mims_pts]

    # Get the final pts to use for TPS
    base_transform = selected_tform

    mims_shapes = [base_transform(mims_shape) for mims_shape in mims_shapes]
    mims_pts = [base_transform(mims_pt) for mims_pt in mims_pts]
    final_em_pts = em_pts.copy()
    final_mims_pts = mims_pts.copy()
    for em, mi in zip(em_shapes, mims_shapes):
        final_em_pts.append(polygon_centroid(em))
        final_mims_pts.append(polygon_centroid(mi))
        final_em_pts.extend(radial_spokes(em))
        final_mims_pts.extend(radial_spokes(mi))

    em_pts = np.asarray(final_em_pts)
    mims_pts = np.asarray(final_mims_pts)
    # Estimate the TPS transform
    tps = ThinPlateSplineTransform()
    tps.estimate(em_pts, mims_pts)

    # Find the bounding box of the MIMS image post TPS
    mims_corners = np.array(
        [[0, 0], [w_mims - 1, 0], [w_mims - 1, h_mims - 1], [0, h_mims - 1]]
    )
    mims_corners = base_transform(mims_corners)
    mims_corners = tps(mims_corners)
    min_x = np.min(mims_corners[:, 0])
    min_y = np.min(mims_corners[:, 1])
    max_x = np.max(mims_corners[:, 0])
    max_y = np.max(mims_corners[:, 1])
    new_width = math.ceil(max_x - min_x)
    new_height = math.ceil(max_y - min_y)

    # 0. translation expressed as simple arithmetic --------------------------
    def apply_translation(pts, dx, dy):
        out = pts.copy()
        out[:, 0] -= dx  #   ← note the sign: translating the *output*
        out[:, 1] -= dy  #     canvas by (–min_x, –min_y)
        return out

    # 1. grid of source-image pixels -----------------------------------------
    # Then load a MIMS isotope image, rotate it, TPS it, and then translate and upscale it
    s32 = image_from_im_file(mims_image.file.path, "32S")
    if mims_image.flip:
        s32 = s32[:, ::-1]
    h_src, w_src = s32.shape
    yy, xx = np.mgrid[0:h_src, 0:w_src].astype(np.float32)
    src_pts = np.column_stack((xx.ravel(), yy.ravel()))

    # 2. forward composite:  Affine  →  TPS  →  Translation
    pts = base_transform(src_pts)  # affine       (float64 → fine)
    pts = tps(pts)  # TPS forward
    dst_pts = apply_translation(pts, min_x, min_y)
    H, W = new_height, new_width
    grid_y, grid_x = np.mgrid[0:H, 0:W]

    # linear interpolation; fill_value = -1 marks holes beyond convex hull
    map_x = griddata(
        dst_pts, src_pts[:, 0], (grid_x, grid_y), method="linear", fill_value=-1
    ).astype(np.float32)
    map_y = griddata(
        dst_pts, src_pts[:, 1], (grid_x, grid_y), method="linear", fill_value=-1
    ).astype(np.float32)
    warped = cv2.remap(
        s32.astype(np.float32),
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return (em_pts, mims_pts)
