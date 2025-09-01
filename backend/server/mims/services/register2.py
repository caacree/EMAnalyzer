# Jupyter cell — stitch every MIMSImage in a Canvas into one big 16-bit PNG per isotope
# ------------------------------------------------------------------------------------
from pathlib import Path
import numpy as np
import cv2
import pyvips
from django.conf import settings
from django.shortcuts import get_object_or_404
from mims.models import (
    Canvas,
    Isotope,
    MIMSImage,
    MIMSOverlay,
    MIMSImageSet,
    get_mosaic_upload_path,
    get_mask_upload_path,
)  # adjust import path if necessary
from skimage.transform import SimilarityTransform, ThinPlateSplineTransform, warp
from PIL import Image
from tifffile import imread, imwrite
from mims.services.image_utils import image_from_im_file
from mims.services.register import (
    validate_mims_image,
    get_mims_dims,
    get_points_transform,
    polygon_centroid,
    _flip_x,
)
import json
from mims.services.debug import _save_debug_overlay

# ───────────────────────── helpers ────────────────────────────────────────────────
ISOTOPES = ["14N 12C", "15N 12C", "13C", "12C", "197Au", "32S"]
UINT8_ISO = {"197Au"}
RATIO_PAIR = ("13C", "12C", "14N 12C", "15N 12C")


def slug(s: str) -> str:
    return s.replace(" ", "_").replace("/", "_")


def blank_canvas(dtype, w, h):
    return np.zeros((h, w), dtype=dtype)


def write_cog_tiff(path: Path, arr: np.ndarray):
    """
    Write `arr` (H×W or H×W×2) as a single-file pyramidal TIFF-COG via libvips.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # determine band count and VIPS dtype
    bands = arr.shape[2] if arr.ndim == 3 else 1
    dtype_str = "ushort" if arr.dtype == np.uint16 else "uchar"
    # build a VIPS image from raw memory
    vips_img = pyvips.Image.new_from_memory(
        arr.tobytes(), arr.shape[1], arr.shape[0], bands, dtype_str
    )
    id_suffix = "/".join(str(path).split("media/")[1].split("/")[0:-1])
    id_path = f"http://localhost:8000{settings.MEDIA_URL}{id_suffix}"
    save_path = str(path)
    if not save_path.endswith(".tif"):
        save_path += ".tif"
    tifffile.imwrite(save_path, arr)
    """
    vips_img.dzsave(
        str(path),
        id=id_path,
        layout=pyvips.enums.ForeignDzLayout.IIIF3,
        suffix=".png[bitdepth=16]",  # 16-bit PNG with alpha
        tile_size=512,
        overlap=0,
        container="fs",  # filesystem directory
        compression=9,  # if you ever zipped it
        skip_blanks=1,  # drop fully-transparent tiles
    )
    with open(str(path) + "/info.json", "r") as f:
        current_info = json.load(f)
    with open(str(path) + "/info.json", "w") as f:
        current_info["tileFormat"] = "png"
        json.dump(current_info, f)
    """


# ───────────────────── registration geometry per-image ───────────────────────────
def registration_geometry(mims_img):
    """Return dict holding warp info that is isotope-independent."""
    (_, em_shapes, mims_shapes, em_pts, mims_pts) = validate_mims_image(mims_img.id)
    h_mims, w_mims = get_mims_dims(mims_img)

    # coarse similarity (+ mirror) ------------------------------------------------
    em_cent = [polygon_centroid(s) for s in em_shapes] + em_pts
    mims_cent = [polygon_centroid(s) for s in mims_shapes] + mims_pts
    base_tf, needs_flip, max_x = get_points_transform(
        mims_img.image_set, np.asarray(mims_cent, float), np.asarray(em_cent, float)
    )
    if needs_flip:
        mims_shapes = [_flip_x(s, max_x) for s in mims_shapes]
        mims_pts = [_flip_x(p, max_x) for p in mims_pts]

    # landmark stacks -------------------------------------------------------------
    mims_stack, em_stack = np.empty((0, 2)), np.empty((0, 2))
    for mp, ep in zip(mims_shapes, em_shapes):
        mims_stack = np.vstack([mims_stack, polygon_centroid(mp)])
        em_stack = np.vstack([em_stack, polygon_centroid(ep)])
    for mp, ep in zip(mims_pts, em_pts):
        mims_stack = np.vstack([mims_stack, mp])
        em_stack = np.vstack([em_stack, ep])

    if len(mims_stack) < 5 or len(em_stack) < 5:
        raise ValueError(f"Not enough landmarks found for image {mims_img.id}")

    mims_pred = base_tf(mims_stack)
    offset = np.median(mims_pred - em_stack, axis=0)

    mims_tf = SimilarityTransform(
        scale=1, rotation=base_tf.rotation, translation=[0, 0]
    )
    em_tf = SimilarityTransform(
        scale=1 / base_tf.scale,
        translation=-(base_tf.translation - offset) / base_tf.scale,
    )

    # ensure everything lives in +ve canvas coords -------------------------------
    mims_corners = np.array(
        [[0, 0], [w_mims - 1, 0], [w_mims - 1, h_mims - 1], [0, h_mims - 1]], float
    )
    if needs_flip:
        mims_corners = _flip_x(mims_corners, max_x)
    em_corners = mims_tf(mims_corners)
    shift = -np.minimum(np.min(em_corners, 0), 0)
    if (shift > 0).any():
        mims_tf = SimilarityTransform(
            scale=1, rotation=base_tf.rotation, translation=shift
        )
        em_tf = SimilarityTransform(
            scale=1 / base_tf.scale,
            translation=-(base_tf.translation - offset) / base_tf.scale + shift,
        )
        em_corners = mims_tf(mims_corners)

    mims_pred = mims_tf(mims_stack)
    em_pred = em_tf(em_stack)
    mims_pred = np.vstack([mims_pred])
    em_pred = np.vstack([em_pred])

    # EM crop box for this image --------------------------------------------------
    canvas_corners = mims_tf(mims_corners)
    em_corners2 = em_tf.inverse(canvas_corners)
    x0, y0 = np.floor(em_corners2.min(0)).astype(int)
    x1, y1 = np.ceil(em_corners2.max(0)).astype(int)
    em_img = np.array(Image.open(mims_img.canvas.images.first().file.path))
    H, W = em_img.shape[:2]
    precrop_bbox = [x0, y0, x1, y1].copy()
    x0, x1 = np.clip([x0, x1], 0, W)
    y0, y1 = np.clip([y0, y1], 0, H)

    height = int(np.ptp(em_corners[:, 1]))
    width = int(np.ptp(em_corners[:, 0]))
    out_shape = (height, width)

    # thin-plate spline -----------------------------------------------------------
    tps = ThinPlateSplineTransform()
    tps.estimate(em_pred, mims_pred)

    return dict(
        needs_flip=needs_flip,
        max_x=max_x,
        mims_tf=mims_tf,
        tps=tps,
        bbox=(x0, y0, x1, y1),
        precrop_bbox=precrop_bbox,
        out_shape=out_shape,
    )


def print_stats(img_name, img):
    vmin, vmax = img.min(), img.max()
    nonzero = np.count_nonzero(img)
    print(
        f"{img_name}  min = {vmin}, max = {vmax}, non-zero pixels = {nonzero} of {img.shape[0]*img.shape[1]}\n"
    )
    return


# ─────────────────────────── patch generator ─────────────────────────────────────
def isotope_patch(mims_img, iso_name, geom):
    """
    Returns:
        patch  : (h, w) uint16 greyscale
        x0, y0 : top-left placement on full canvas
    """
    name = mims_img.name
    src = image_from_im_file(mims_img.file.path, iso_name, autocontrast=False)
    if geom["needs_flip"]:
        src = src[:, ::-1]

    img_pre = warp(
        src,
        geom["mims_tf"].inverse,
        output_shape=geom["out_shape"],
        preserve_range=True,
        order=0,
    )
    # If this fails, it might be because all the points got duplicated, check the app to see if they all have 2 set
    img_post = warp(
        img_pre,
        geom["tps"],
        output_shape=geom["out_shape"],
        preserve_range=True,
        order=0,
    )
    img = img_post

    # build binary mask once to zero background
    ones = np.ones_like(src, np.uint8)
    mask = warp(
        ones,
        geom["mims_tf"].inverse,
        order=0,
        output_shape=geom["out_shape"],
        cval=0,
        preserve_range=True,
    )
    mask = warp(
        mask,
        geom["tps"],
        order=0,
        output_shape=geom["out_shape"],
        cval=0,
        preserve_range=True,
    )

    x0, y0, x1, y1 = geom["bbox"]
    x0p, y0p, x1p, y1p = geom["precrop_bbox"]
    xcrop_start = max(0, x0 - x0p)
    xcrop_end = x1 - x1p
    if xcrop_end >= 0:
        xcrop_end = x1
    ycrop_start = max(0, y0 - y0p)
    ycrop_end = y1 - y1p
    if ycrop_end >= 0:
        ycrop_end = y1

    resized_img = cv2.resize(
        img, (x1p - x0p, y1p - y0p), interpolation=cv2.INTER_NEAREST
    )
    resized_mask = cv2.resize(
        mask, (x1p - x0p, y1p - y0p), interpolation=cv2.INTER_NEAREST
    )
    crop_x_start = x0 - x0p
    crop_y_start = y0 - y0p

    # 3. Calculate the dimensions of the final *visible* patch.
    patch_width = x1 - x0
    patch_height = y1 - y0

    # 4. Perform the slice to get the correctly cropped patch.
    img = resized_img[
        crop_y_start : crop_y_start + patch_height,
        crop_x_start : crop_x_start + patch_width,
    ]

    mask = resized_mask[
        crop_y_start : crop_y_start + patch_height,
        crop_x_start : crop_x_start + patch_width,
    ]

    patch = np.clip(img, 0, 65535).astype(np.uint16)
    patch[mask == 0] = 0
    # _save_debug_overlay(mims_img, geom, patch, iso_name)
    return patch, x0, y0


# ─────────────────────────── main driver ─────────────────────────────────────────
def stitch_canvas(canvas_name: str) -> MIMSImageSet:
    canvas = get_object_or_404(Canvas, name=canvas_name)
    mset = MIMSImageSet.objects.filter(canvas=canvas).order_by("-created_at")
    if not mset:
        raise RuntimeError(f"No MIMSImageSet found for canvas {canvas_name}")
    for mset in mset:
        stitch_canvas_from_set(mset)
    return canvas


import tifffile


def stitch_canvas_from_set(mset: MIMSImageSet) -> MIMSImageSet:
    print(f"Stitching {mset.id} - from {mset.created_at}")
    canvas = mset.canvas
    mset.status = "REGISTERING"
    mset.save(update_fields=["status"])
    MIMSOverlay.objects.filter(image_set=mset).delete()

    # pre-compute warp geometry once per MIMSImage
    geom_cache = {}
    for m in MIMSImage.objects.filter(canvas=canvas):
        try:
            print(m.file.path)
            geom_cache[m.id] = registration_geometry(m)
        except Exception as e:
            print(f"Error registering {m.id}: {e}")
            continue
    if not geom_cache:
        raise RuntimeError("No images could be registered—abort.")

    # each geom["bbox"] is (x0,y0,x1,y1) on the full EM canvas
    xs0, ys0, xs1, ys1 = zip(*(g["bbox"] for g in geom_cache.values()))
    x0_all = int(min(xs0))
    y0_all = int(min(ys0))
    x1_all = int(max(xs1))
    y1_all = int(max(ys1))
    mset.canvas_bbox = [
        [x0_all, y0_all],
        [x1_all, y0_all],
        [x1_all, y1_all],
        [x0_all, y1_all],
    ]
    print(f"Mset canvas bbox: {mset.canvas_bbox}")
    mset.save(update_fields=["canvas_bbox"])

    # hold these two for the later ratio
    ratio_bufs = {}
    mask_full = np.zeros((canvas.height, canvas.width), dtype=bool)
    for iso in ISOTOPES:
        print(f"Stitching {iso}")
        use_u8 = iso in UINT8_ISO
        dtype = np.uint8 if use_u8 else np.uint16
        big = blank_canvas(dtype, canvas.width, canvas.height)
        mask_full |= big > 0

        for mims_img in MIMSImage.objects.filter(
            image_set=mset, id__in=geom_cache.keys()
        ).order_by("-name"):
            if (
                not mims_img.isotopes.filter(name=iso).exists()
                or mims_img.id not in geom_cache
            ):
                continue
            patch, x0, y0 = isotope_patch(mims_img, iso, geom_cache[mims_img.id])
            if use_u8:
                patch = np.clip(patch, 0, 255).astype(np.uint8)

            h, w = patch.shape
            region = big[y0 : y0 + h, x0 : x0 + w]

            try:
                write_mask = (patch > 0) & (region == 0)  # only paint where dst==0
                region[write_mask] = patch[write_mask]
            except Exception as e:
                print(f"Error writing {iso} to {mims_img.name}: {e}")
                print(f"Dims are {canvas.width}x{canvas.height}")
                print(
                    f"patch: {patch.shape}, region: {region.shape}, x0: {x0}, w: {w}, y0: {y0}, h: {h}"
                )
                raise e
            big[y0 : y0 + h, x0 : x0 + w] = region

        # — crop to the set’s bbox

        xs = [pt[0] for pt in mset.canvas_bbox]
        ys = [pt[1] for pt in mset.canvas_bbox]
        x0c, x1c = int(min(xs)), int(max(xs))
        y0c, y1c = int(min(ys)), int(max(ys))
        big_crop = big[y0c:y1c, x0c:x1c]

        # — build two-channel (L + α) array
        lum = big_crop
        alpha = (big_crop > 0).astype(np.uint8) * 255
        la = np.stack([lum, alpha], axis=-1)

        # — persist to Django and storage
        isotope_obj, _ = Isotope.objects.get_or_create(name=iso)
        overlay = MIMSOverlay.objects.create(image_set=mset, isotope=isotope_obj)
        fp = Path(settings.MEDIA_ROOT) / get_mosaic_upload_path(overlay, f"{slug(iso)}")
        write_cog_tiff(fp, la)
        overlay.mosaic.name = fp.relative_to(settings.MEDIA_ROOT).as_posix() + ".tif"
        overlay.save(update_fields=["mosaic"])
        print(f"✓ saved overlay for {iso} → {overlay.mosaic.name}")

        if iso in RATIO_PAIR:  # keep for later ratio
            ratio_bufs[iso] = big.astype(np.uint32)  # promote to avoid overflow

    single_denom = True

    # ------------- build the 13C ratio (13C / (13C+12C) * 10 000) --------------
    print("Computing 13C_ratio …")
    c13 = ratio_bufs["13C"]
    c12 = ratio_bufs["12C"]
    if single_denom:
        denom = c12
    else:
        denom = c13 + c12

    ratio = np.zeros_like(c13, dtype=np.float32)
    np.divide(c13, denom, out=ratio, where=denom > 0)
    ratio = (ratio * 1.0e4).round()
    if single_denom:
        ratio[np.isnan(ratio)] = 0
        ratio[np.isinf(ratio)] = 30000
        ratio[ratio >= 30000] = 30000
    ratio_u16 = np.clip(ratio, 0, 65535).astype(np.uint16)
    isotope_obj, _ = Isotope.objects.get_or_create(name="13C_ratio")
    ratio_overlay = MIMSOverlay.objects.create(image_set=mset, isotope=isotope_obj)
    fp = Path(settings.MEDIA_ROOT) / get_mosaic_upload_path(
        ratio_overlay, "13C_ratio.tif"
    )
    write_cog_tiff(fp, ratio_u16)
    ratio_overlay.mosaic.name = fp.relative_to(settings.MEDIA_ROOT).as_posix()
    ratio_overlay.save(update_fields=["mosaic"])

    # ------------- build the 15N_ratio (15N / (15N+14N) * 10 000) --------------
    print("Computing 15N_ratio …")
    n15 = ratio_bufs["15N 12C"]
    n14 = ratio_bufs["14N 12C"]
    if single_denom:
        denom = n14
    else:
        denom = n14 + n15
    ratio = np.zeros_like(n14, dtype=np.float32)
    np.divide(n15, denom, out=ratio, where=denom > 0)
    ratio = (ratio * 1.0e4).round()
    if single_denom:
        ratio[np.isnan(ratio)] = 0
        ratio[np.isinf(ratio)] = 30000
        ratio[ratio >= 30000] = 30000
    ratio_u16 = np.clip(ratio, 0, 65535).astype(np.uint16)
    isotope_obj, _ = Isotope.objects.get_or_create(name="15N_ratio")
    ratio_overlay = MIMSOverlay.objects.create(image_set=mset, isotope=isotope_obj)
    fp = Path(settings.MEDIA_ROOT) / get_mosaic_upload_path(
        ratio_overlay, "15N_ratio.tif"
    )
    write_cog_tiff(fp, ratio_u16)
    ratio_overlay.mosaic.name = fp.relative_to(settings.MEDIA_ROOT).as_posix()
    ratio_overlay.save(update_fields=["mosaic"])

    # crop & save
    mask_crop = mask_full[y0c:y1c, x0c:x1c].astype(np.uint8)
    mask_fp = Path(settings.MEDIA_ROOT) / get_mask_upload_path(mset, "mask.tif")
    write_cog_tiff(mask_fp, mask_crop)
    mset.mask.name = mask_fp.relative_to(settings.MEDIA_ROOT).as_posix()
    mset.save(update_fields=["mask"])
    print(f"✓ saved shared mask → {mset.mask.name}")

    # mark done
    mset.status = "DONE"
    mset.save(update_fields=["status"])
    return mset
