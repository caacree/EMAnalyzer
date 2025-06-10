import json
import math
import time
from django.shortcuts import get_object_or_404
from mims.models import MimsTiffImage
import tifffile
from mims.services.image_utils import image_from_im_file
from mims.services.orient_images import get_points_transform
from mims.models import MIMSImage
from django.core.files import File
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
    radial_spokes,
)
from django.shortcuts import get_object_or_404
from mims.models import MIMSImage
import time


def load_shapes(mims_image):
    mims_path = Path(mims_image.file.path)
    shapes_json_path = Path(
        mims_path.parent / mims_path.stem / "registration" / "reg_shapes.json"
    )

    json_shapes = None
    if not shapes_json_path.exists():
        raise FileNotFoundError(f"Shape file not found: {shapes_json_path}")
    try:
        with open(shapes_json_path, "r") as f:
            json_shapes = json.load(f)
    except Exception as e:
        raise IOError(f"Error reading/parsing {shapes_json_path}: {e}") from e
    return json_shapes


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

    json_shapes = load_shapes(mims_image)
    em_shapes = [np.array(s, dtype=float) for s in json_shapes.get("em_shapes", [])]
    mims_shapes = [np.array(s, dtype=float) for s in json_shapes.get("mims_shapes", [])]
    em_pts = [np.array(s, dtype=float) for s in json_shapes.get("em_points", [])]
    mims_pts = [np.array(s, dtype=float) for s in json_shapes.get("mims_points", [])]
    em_shapes = [
        s for s in em_shapes if s.ndim == 2 and s.shape[0] >= 3 and s.shape[1] >= 2
    ]
    mims_shapes = [
        s for s in mims_shapes if s.ndim == 2 and s.shape[0] >= 3 and s.shape[1] >= 2
    ]
    total_em_points = len(em_pts) + len(em_shapes)
    total_mims_points = len(mims_pts) + len(mims_shapes)
    if total_em_points == 0 or total_mims_points == 0:
        raise ValueError("No valid MIMS or EM shapes found.")
    if total_em_points != total_mims_points:
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

    em_centroids = [polygon_centroid(ep) for ep in em_shapes]
    mims_centroids = [polygon_centroid(mp) for mp in mims_shapes]
    em_centroids.extend(em_pts)
    mims_centroids.extend(mims_pts)

    # --- Get Initial Transform ---
    image_view_set = mims_image.image_set

    selected_tform, needs_flip, _ = get_points_transform(
        image_view_set, np.array(mims_centroids), np.array(em_centroids)
    )
    h_mims, w_mims = get_mims_dims(mims_image)

    # Do the flip transformation if needed
    mims_image.flip = needs_flip
    mims_image.save(update_fields=["flip"])
    if needs_flip:
        mims_shapes_flipped = []
        mims_pts_flipped = []
        for mims_shape in mims_shapes:
            mims_shapes_flipped.append(
                [[(w_mims - 1) - pt[0], pt[1]] for pt in mims_shape]
            )
        for pt in mims_pts:
            mims_pts_flipped.append([(w_mims - 1) - pt[0], pt[1]])
        mims_shapes = mims_shapes_flipped
        mims_pts = mims_pts_flipped

    # Get the final pts to use for TPS
    base_transform = selected_tform

    mims_shapes = [base_transform(mims_shape) for mims_shape in mims_shapes]
    mims_pts = [base_transform(mims_pt)[0] for mims_pt in mims_pts]
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
    yy, xx = np.mgrid[0:h_mims, 0:w_mims].astype(np.float32)
    src_pts = np.column_stack((xx.ravel(), yy.ravel()))
    # 2. forward composite:  Affine  →  TPS  →  Translation
    pts = base_transform(src_pts)  # affine       (float64 → fine)
    pts = tps(pts)  # TPS forward
    dst_pts = apply_translation(pts, min_x, min_y)
    print("after apply translation", time.time() - start_time)
    H, W = new_height, new_width
    grid_y, grid_x = np.mgrid[0:H, 0:W]

    # linear interpolation; fill_value = -1 marks holes beyond convex hull
    map_x = griddata(
        dst_pts, src_pts[:, 0], (grid_x, grid_y), method="linear", fill_value=-1
    ).astype(np.float32)
    map_y = griddata(
        dst_pts, src_pts[:, 1], (grid_x, grid_y), method="linear", fill_value=-1
    ).astype(np.float32)
    reg_loc = Path(mims_image.file.path).with_suffix("") / "registration"
    map_path = reg_loc / "warp_maps_float32.npz"
    np.savez_compressed(map_path, map_x=map_x, map_y=map_y)
    print("after savez", time.time() - start_time)
    new_bbox = [
        [int(min_y), int(min_x)],
        [int(max_y), int(min_x)],
        [int(max_y), int(max_x)],
        [int(min_y), int(max_x)],
    ]
    mims_image.canvas_bbox = new_bbox
    mims_image.save(update_fields=["canvas_bbox"])
    # delete all existing tiff images
    mims_image.mims_tiff_images.all().delete()
    # create new tiff images
    print("pre unwarp", time.time() - start_time)
    for isotope in mims_image.isotopes.all():
        unwarp_mims_image(mims_image, isotope.name, map_x, map_y)
    print("post unwarp", time.time() - start_time)
    mims_image.status = "DEWARPED_ALIGNED"
    mims_image.save(update_fields=["status"])
    print("done")
    return True


def unwarp_mims_image(mims_image, isotope_name, map_x, map_y):
    raw = image_from_im_file(mims_image.file.path, isotope_name, autocontrast=False)
    reg_loc = Path(mims_image.file.path).with_suffix("") / "registration"
    if raw is None:
        return
    if mims_image.flip:
        raw = raw[:, ::-1]

    warped_img = cv2.remap(
        raw.astype(np.float32),  # source
        map_x,
        map_y,  # maps we just saved
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    ).astype(raw.dtype)

    out_path = reg_loc / f"{isotope_name}_unwarped.png"
    warped_png = warped_img.astype(np.uint16)
    cv2.imwrite(str(out_path), warped_png, [cv2.IMWRITE_PNG_COMPRESSION, 0])
    with open(out_path, "rb") as fh:
        MimsTiffImage.objects.create(
            mims_image=mims_image,
            image=File(fh, name=out_path.name),
            name=f"{isotope_name}",
            registration_bbox=mims_image.canvas_bbox,
        )
    os.remove(out_path)
