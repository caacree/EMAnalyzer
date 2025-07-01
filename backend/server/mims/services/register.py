import json
import math
import time
import pandas as pd
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
from PIL import Image
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
from skimage.transform import SimilarityTransform


def _as_int(v):
    return int(v)


def load_shapes(mims_image):
    if mims_image.registration_info:
        return mims_image.registration_info
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
    em_pts = json_shapes.get("em_points", [])
    em_pts = [[p[1], p[0]] for p in em_pts]
    em_pts = [np.array(s, dtype=float) for s in em_pts]
    mims_pts = json_shapes.get("mims_points", [])
    mims_pts = [[p[1], p[0]] for p in mims_pts]
    mims_pts = [np.array(s, dtype=float) for s in mims_pts]
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


# ------------------------------------------------------------------
def _flip_x(arr, max_x):
    arr = np.asarray(arr, float).copy()
    if arr.ndim == 1:
        arr[0] = max_x - arr[0]
    else:
        arr[:, 0] = max_x - arr[:, 0]
    return arr


def _flip_x(arr, max_x):
    arr = np.asarray(arr, float).copy()
    if arr.ndim == 1:
        arr[0] = max_x - arr[0]
    else:
        arr[:, 0] = max_x - arr[:, 0]
    return arr


def register_images(mims_image_obj_id):
    """
    1) Optional X-mirror of MIMS landmarks (same axis get_points_transform used)
    2) Similarity affine             →  EM_pred
    3) Median-offset tweak on translation
    4) Thin-plate spline on residuals (EM_pred → EM_true)
    5) Build inverse warp maps + canvas_bbox
    6) Display diagnostic plots (TPS panel now uses skimage.transform.warp)
    """
    start_time = time.time()

    # ---------- 0. objects & basic geometry ------------------------
    try:
        mims_img, em_shapes, mims_shapes, em_pts, mims_pts = validate_mims_image(
            mims_image_obj_id
        )
    except Exception as e:
        print(e)
        return False
    h_mims, w_mims = get_mims_dims(mims_img)

    # ---------- 1. coarse similarity (with optional mirror) --------
    em_cent = [polygon_centroid(e) for e in em_shapes] + em_pts
    mims_cent = [polygon_centroid(m) for m in mims_shapes] + mims_pts

    base_tf, needs_flip, max_x = get_points_transform(
        mims_img.image_set,
        np.asarray(mims_cent, float),
        np.asarray(em_cent, float),
    )

    if needs_flip:
        mims_shapes = [_flip_x(s, max_x) for s in mims_shapes]
        mims_pts = [_flip_x(p, max_x) for p in mims_pts]

    # ---------- 2. landmark arrays after affine --------------------
    mims_stack, em_stack = np.empty((0, 2)), np.empty((0, 2))
    for mp, ep in zip(mims_shapes, em_shapes):
        mims_stack = np.vstack([mims_stack, polygon_centroid(mp)])
        em_stack = np.vstack([em_stack, polygon_centroid(ep)])
    for mp, ep in zip(mims_pts, em_pts):
        mims_stack = np.vstack([mims_stack, mp])
        em_stack = np.vstack([em_stack, ep])

    #   2a. Initial affine prediction --------------------------------------
    mims_pred = base_tf(mims_stack.copy())

    # ---------- 3. median offset tweak -----------------------------
    delta = mims_pred - em_stack
    offset = np.median(delta, axis=0)
    mims_tf = SimilarityTransform(
        scale=1, rotation=base_tf.rotation, translation=[0, 0]
    )
    em_tf = SimilarityTransform(
        scale=1 / base_tf.scale,
        translation=-(base_tf.translation - offset) / base_tf.scale,
    )

    #   add image corners so the TPS controls the entire canvas -----
    mims_corners = np.array(
        [[0, 0], [w_mims - 1, 0], [w_mims - 1, h_mims - 1], [0, h_mims - 1]],
        dtype=float,
    )
    if needs_flip:
        mims_corners = _flip_x(mims_corners, max_x)
    em_corners = mims_tf(mims_corners)
    min_xy = np.min(em_corners, axis=0)
    max_xy = np.max(em_corners, axis=0)
    shift = -np.minimum(min_xy, 0)
    if (shift > 0).any():
        # rebuild the two similarity transforms **with the shift added**
        mims_tf = SimilarityTransform(
            scale=1, rotation=base_tf.rotation, translation=shift  # <-- NEW
        )

        em_tf = SimilarityTransform(
            scale=1 / base_tf.scale,
            translation=(  # original → plus the same shift
                -(base_tf.translation - offset) / base_tf.scale + shift
            ),
        )
    em_corners = mims_tf(mims_corners)

    mims_pred = mims_tf(mims_stack)
    em_pred = em_tf(em_stack)

    mims_pred = np.vstack([mims_pred, em_corners])
    em_pred = np.vstack([em_pred, em_corners])

    # ---------- 4. thin-plate spline fit ---------------------------
    tps = ThinPlateSplineTransform()
    # NOTE: we pass (dst, src) so that `tps` is the **inverse** map,
    #       exactly what `skimage.transform.warp` expects
    tps.estimate(em_pred, mims_pred)
    tps_inv = ThinPlateSplineTransform()
    tps_inv.estimate(mims_pred, em_pred)

    # ---------- 6. Get the EM BBOX ------------------------------
    canvas_corners = mims_tf(mims_corners)
    em_corners = em_tf.inverse(canvas_corners)
    x0, y0 = np.floor(em_corners.min(axis=0)).astype(int)
    x1, y1 = np.ceil(em_corners.max(axis=0)).astype(int)

    # clamp to the EM image limits (in case any indices went slightly <0 or >size-1)
    em_img = np.array(Image.open(mims_img.canvas.images.first().file.path))
    H, W = em_img.shape[:2]
    x0, x1 = np.clip([x0, x1], 0, W)
    y0, y1 = np.clip([y0, y1], 0, H)

    # ---------- 6. save bbox & regenerate TIFFs --------------------
    mims_img.canvas_bbox = [
        [int(x0), int(y0)],
        [int(x1), int(y0)],
        [int(x1), int(y1)],
        [int(x0), int(y1)],
    ]
    mims_img.mims_tiff_images.all().delete()
    mims_img.save(update_fields=["canvas_bbox"])
    output_shape = [int(max_xy[1] - min_xy[1]), int(max_xy[0] - min_xy[0])]

    for tiff in mims_img.mims_tiff_images.all():
        tiff.image.delete(save=False)
        tiff.delete()
    mims_img.mims_tiff_images.all().delete()
    t0 = time.time()
    for iso in mims_img.isotopes.all():
        # ------------ 1. read + optional flip -------------------------
        src = image_from_im_file(mims_img.file.path, iso.name, autocontrast=False)
        if needs_flip:
            src = src[:, ::-1]

        # ------------ 2. warp intensity image -------------------------
        img = warp(src, mims_tf.inverse, output_shape=output_shape, preserve_range=True)
        img = warp(img, tps, output_shape=output_shape, preserve_range=True)

        # ------------ 3. build alpha mask (warp of ones) --------------
        ones = np.ones_like(src, dtype=np.uint8)
        mask = warp(
            ones,
            mims_tf.inverse,
            output_shape=output_shape,
            order=0,
            cval=0,
            preserve_range=True,
        )
        mask = warp(
            mask, tps, output_shape=output_shape, order=0, cval=0, preserve_range=True
        )

        # ------------ 4. crop / resize both the same ------------------
        img = cv2.resize(img, (y1 - y0, x1 - x0), interpolation=cv2.INTER_LINEAR)
        mask = cv2.resize(mask, (y1 - y0, x1 - x0), interpolation=cv2.INTER_NEAREST)

        # ------------ 5. build 4-channel BGRA array -------------------
        img_u8 = np.clip(img, 0, 255).astype(np.uint8)
        alpha = (mask > 0.5).astype(np.uint8) * 255  # 0 or 255
        rgba = cv2.merge([img_u8, img_u8, img_u8, alpha])

        # ------------ 6. write lossless PNG ---------------------------
        reg_loc = Path(mims_img.file.path).with_suffix("") / "registration"
        out_path = reg_loc / f"{iso.name}_unwarped.png"
        cv2.imwrite(
            str(out_path), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 0]
        )  # 0 = no compression

        # ------------ 7. store in DB, then delete temp ---------------
        with open(out_path, "rb") as fh:
            tiff = MimsTiffImage.objects.create(
                mims_image=mims_img,
                image=File(fh, name=out_path.name),
                name=f"{iso.name}",
                registration_bbox=mims_img.canvas_bbox,
            )
            print(tiff.image.path)
        out_path.unlink()
    print("unwarp time:", round(time.time() - t0, 1), "s")

    mims_img.status = "DEWARPED_ALIGNED"
    mims_img.save(update_fields=["status"])
    print("done")
    return True
