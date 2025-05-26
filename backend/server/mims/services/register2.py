import json
import math
import time
from django.shortcuts import get_object_or_404

# Assume these are correctly implemented and imported
# from mims.services.image_utils import image_from_im_file
# from mims.services.orient_images import get_points_transform
import tifffile
from mims.services.unwarp import make_unwarp_transform, make_unwarp_images
from mims.services.image_utils import image_from_im_file
from mims.services.orient_images import get_points_transform
from skimage.transform import estimate_transform, SimilarityTransform, AffineTransform
from skimage.draw import polygon
from skimage.transform import warp
import sims
from mims.models import MIMSImage
import os
from pathlib import Path
import numpy as np


# --- Helper Functions (assuming polygon_centroid, image_from_im_file, get_points_transform exist) ---
# Placeholder implementations for standalone testing:
def polygon_centroid(polygon):
    try:
        poly_array = np.array(polygon, dtype=float)
        if poly_array.ndim != 2 or poly_array.shape[1] < 2:
            raise ValueError("Polygon must be an NxK array with K >= 2.")
        return np.mean(poly_array[:, :2], axis=0)
    except Exception as e:
        raise ValueError(f"Invalid data during centroid calculation: {e}")


def register_images2_test(mims_image_obj_id, shrink_em=False):
    start_time = time.time()
    # --- Get MIMS Object and Paths ---
    try:
        mims_image = get_object_or_404(MIMSImage, pk=mims_image_obj_id)
    except Exception as e:
        raise ValueError(f"Could not find MIMSImage ID {mims_image_obj_id}: {e}") from e

    if (
        not mims_image.file
        or not hasattr(mims_image.file, "path")
        or not mims_image.file.path
    ):
        raise ValueError(f"MIMSImage {mims_image_obj_id} lacks a valid file path.")
    mims_path = Path(mims_image.file.path)
    if not mims_path.exists():
        raise FileNotFoundError(f"MIMS file not found: {mims_path}")

    reg_loc = mims_path.parent / mims_path.stem / "registration"
    os.makedirs(reg_loc, exist_ok=True)
    print(f"Registration directory: {reg_loc}")

    # --- Load Shapes ---
    shapes_json_path = reg_loc / "reg_shapes.json"
    if not shapes_json_path.exists():
        raise FileNotFoundError(f"Shape file not found: {shapes_json_path}")
    try:
        with open(shapes_json_path, "r") as f:
            json_shapes = json.load(f)
    except Exception as e:
        raise IOError(f"Error reading/parsing {shapes_json_path}: {e}") from e

    # --- Validate and Prepare Shapes & Centroids ---
    try:
        em_shapes = [np.array(s, dtype=float) for s in json_shapes.get("em_shapes", [])]
        mims_shapes = [
            np.array(s, dtype=float) for s in json_shapes.get("mims_shapes", [])
        ]
        em_shapes = [
            s for s in em_shapes if s.ndim == 2 and s.shape[0] >= 3 and s.shape[1] >= 2
        ]
        mims_shapes = [
            s
            for s in mims_shapes
            if s.ndim == 2 and s.shape[0] >= 3 and s.shape[1] >= 2
        ]

        if not mims_shapes or not em_shapes:
            raise ValueError("No valid MIMS or EM shapes found.")
        if len(mims_shapes) != len(em_shapes):
            raise ValueError("MIMS and EM shape lists differ in length.")

        em_centroids = np.array([polygon_centroid(ep) for ep in em_shapes])
        mims_centroids = np.array([polygon_centroid(mp) for mp in mims_shapes])
        print(f"DEBUG: Using {len(mims_centroids)} valid shape pairs.")
    except Exception as e:
        raise ValueError(f"Error processing shapes/centroids: {e}") from e

    # --- Get Initial Transform ---
    if not hasattr(mims_image, "image_set") or not mims_image.image_set:
        raise ValueError("MIMSImage object lacks related ImageViewSet.")
    image_view_set = mims_image.image_set
    try:
        selected_tform, needs_flip, _ = get_points_transform(
            image_view_set, mims_centroids, em_centroids
        )
    except Exception as e:
        raise RuntimeError(f"Error during get_points_transform: {e}") from e

    print(f"--- Initial Transform Analysis ---")
    print(f"DEBUG: Needs Flip: {needs_flip}")
    base_transform = selected_tform
    print(f"DEBUG: Base Transform (selected_tform) Params:\n{base_transform.params}")
    # ... (Optional: print rotation/determinant) ...
    print(f"---------------------------------")

    # --- Load ALL MIMS Isotope Data ---
    print("Loading all required isotope data...")
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

    # --- Calculate Target Geometry and Output Shape (ONCE) --- <<< INSERTED MISSING BLOCK
    print(f"--- Calculating Target Geometry (shrink_em={shrink_em}) ---")
    _T_target_geom = None
    if shrink_em:
        # Use scale=1 logic
        print("Applying Shrink Logic (Target Scale=1, Centered on Flipped MIMS)")
        matrix_base = base_transform.params
        det_base = np.linalg.det(matrix_base[:2, :2])
        scale_base = np.sqrt(det_base) if det_base > 1e-10 else 0.0
        if scale_base < 1e-9:
            raise ValueError(
                f"Base transform scale near zero ({scale_base:.2g}). Cannot shrink."
            )
        M_rot_target = matrix_base[:2, :2] / scale_base
        img_center = np.array([w_mims / 2.0, h_mims / 2.0])
        rotated_center_origin = M_rot_target @ img_center
        T_final_trans = img_center - rotated_center_origin
        final_matrix_target = np.identity(3)
        final_matrix_target[:2, :2] = M_rot_target
        final_matrix_target[:2, 2] = T_final_trans
        _T_target_geom = AffineTransform(matrix=final_matrix_target)
    else:
        # Use original transform (maps to EM scale/space)
        print("No Shrink: Target space is EM space")
        _T_target_geom = base_transform

    T_final_warp = _T_target_geom  # This maps (flipped) MIMS -> Target Content
    print(f"DEBUG: T_final_warp Matrix:\n{T_final_warp.params}")

    print("--- Calculating Output Geometry & Inverse Warp Transform (Once) ---")
    corners = np.array([[0.0, 0.0], [w_mims, 0.0], [w_mims, h_mims], [0.0, h_mims]])
    transformed_corners = T_final_warp(corners)
    min_coords = np.min(transformed_corners, axis=0)
    max_coords = np.max(transformed_corners, axis=0)
    content_width = max_coords[0] - min_coords[0]
    content_height = max_coords[1] - min_coords[1]
    padding_factor = 0.05
    padding_x = (
        max(1, int(np.ceil(content_width * padding_factor)))
        if content_width > 1e-6
        else 0
    )
    padding_y = (
        max(1, int(np.ceil(content_height * padding_factor)))
        if content_height > 1e-6
        else 0
    )
    padding_vec = np.array([padding_x, padding_y])  # Define padding_vec here
    output_width = int(np.ceil(content_width)) + 2 * padding_x
    output_height = int(np.ceil(content_height)) + 2 * padding_y
    if output_width <= 0 or output_height <= 0:
        if content_width < 1e-6 and content_height < 1e-6:
            output_width, output_height = 1, 1
        else:
            raise ValueError(
                f"Invalid output dims: W={output_width}, H={output_height}"
            )
    output_shape = (output_height, output_width)  # DEFINE output_shape
    print(f"DEBUG: Final Output Shape (H, W): {output_shape}")

    try:
        T_final_warp_inv = T_final_warp.inverse
    except np.linalg.LinAlgError:
        raise ValueError("Could not invert T_final_warp.")

    T_shift_output_to_content = np.identity(3)
    T_shift_output_to_content[:2, 2] = min_coords - padding_vec
    M_warp_inverse = (
        T_final_warp_inv.params @ T_shift_output_to_content
    )  # DEFINE M_warp_inverse
    print(
        f"DEBUG: M_warp_inverse Matrix (Output Grid -> Flipped MIMS Input):\n{M_warp_inverse}"
    )
    print(f"-----------------------------------------------------------")
    # --- END OF INSERTED BLOCK ---

    # --- Loop through pre-loaded data and Warp ---
    print("\n--- Warping Isotope Images ---")
    warped_isotopes_list = []  # Collect warped images
    last_output_filepath = None  # To return one path

    for i, isotope_name in enumerate(isotope_names):  # Iterate using names and index
        print(f"Processing isotope: {isotope_name}")
        img_mims = mims_data_cube[i, :, :]  # Get the slice for this isotope

        img_to_warp = img_mims
        if needs_flip:
            img_to_warp = np.fliplr(img_mims)
        img_to_warp = np.ascontiguousarray(img_to_warp)

        print(f"Applying warp to {isotope_name}...")
        t_warp_start = time.time()
        try:
            # Use the pre-calculated M_warp_inverse and output_shape
            warped_img = warp(
                img_to_warp,
                M_warp_inverse,  # Use calculated inverse warp
                output_shape=output_shape,  # Use calculated output shape
                order=1,
                preserve_range=True,
                mode="constant",
                cval=0,
            )
            print(
                f"Warp for {isotope_name} finished in {time.time() - t_warp_start:.2f} sec."
            )
            # Type Conversion
            if img_mims.dtype != warped_img.dtype:
                if np.issubdtype(img_mims.dtype, np.integer):
                    dtype_info = np.iinfo(img_mims.dtype)
                    final_image = np.clip(warped_img, dtype_info.min, dtype_info.max)
                    final_image = np.rint(final_image).astype(img_mims.dtype)
                elif np.issubdtype(img_mims.dtype, np.floating):
                    final_image = warped_img.astype(img_mims.dtype)
                else:
                    final_image = warped_img.astype(img_mims.dtype)
            else:
                final_image = warped_img

            warped_isotopes_list.append(final_image)  # Add converted image

            # Saving individual warped files (optional, can be replaced by multi-channel save later)
            output_filepath = reg_loc / f"{isotope_name}_warped.tiff"
            stats = f"min={np.min(final_image)}, max={np.max(final_image)}, mean={np.mean(final_image):.2f}, dtype={final_image.dtype}"
            print(f"DEBUG: Final {isotope_name} image stats: {stats}")
            if np.max(final_image) == 0 and np.min(final_image) == 0:
                print(f"WARNING: Final {isotope_name} image content is all zeros.")
            try:
                tifffile.imwrite(output_filepath, final_image, photometric="minisblack")
                last_output_filepath = output_filepath  # Store last successful path
            except Exception as e:
                print(f"Error writing output TIFF {output_filepath}: {e}")

        except Exception as e:
            print(f"Error during skimage.warp for {isotope_name}: {e}")
            # Append None or handle error as needed if saving multichannel later
            continue

    print("--- Isotope Warping Finished ---")

    # --- Mask Generation ---
    print("\n--- Generating Masks ---")
    mims_mask_array = np.zeros(output_shape, dtype=np.uint8)  # Use calculated shape
    em_mask_array = np.zeros(output_shape, dtype=np.uint8)  # Use calculated shape

    try:
        M_FLIPPED_MIMS_to_OUTPUT = np.linalg.inv(M_warp_inverse)
        T_FLIPPED_MIMS_to_OUTPUT = AffineTransform(matrix=M_FLIPPED_MIMS_to_OUTPUT)
        # print(f"DEBUG: T_FLIPPED_MIMS_to_OUTPUT:\n{T_FLIPPED_MIMS_to_OUTPUT.params}") # Optional debug
    except np.linalg.LinAlgError:
        raise ValueError("Fatal: Could not get forward transform for mask generation.")

    try:
        T_EM_to_FLIPPED_MIMS = selected_tform.inverse
        # print(f"DEBUG: T_EM_to_FLIPPED_MIMS:\n{T_EM_to_FLIPPED_MIMS.params}") # Optional debug
    except np.linalg.LinAlgError:
        raise ValueError("Could not invert selected_tform for EM mask processing.")

    # Full Alignment Transform: EM -> Output Grid
    T_EM_to_OUTPUT_aligned = T_FLIPPED_MIMS_to_OUTPUT + T_EM_to_FLIPPED_MIMS

    # --- Process MIMS Shapes ---
    print("Transforming and rasterizing MIMS shapes...")
    mims_pixels_drawn = 0
    mims_shapes_to_transform = mims_shapes
    if needs_flip:
        # (Flip MIMS coordinates - code omitted for brevity, same as before)
        mims_shapes_flipped_coords = []
        for shape in mims_shapes:
            flipped_shape = shape.copy()
            flipped_shape[:, 0] = (w_mims - 1.0) - flipped_shape[:, 0]
            mims_shapes_flipped_coords.append(flipped_shape)
        mims_shapes_to_transform = mims_shapes_flipped_coords

    final_mims_centroids = []
    for i, shape in enumerate(mims_shapes_to_transform):
        if shape.shape[0] < 3:
            continue
        transformed_shape = T_FLIPPED_MIMS_to_OUTPUT(shape[:, :2])
        final_mims_centroids.append(polygon_centroid(transformed_shape))
        rows = np.clip(transformed_shape[:, 1], 0, output_shape[0] - 1)
        cols = np.clip(transformed_shape[:, 0], 0, output_shape[1] - 1)
        try:
            rr, cc = polygon(rows, cols, output_shape)
            if rr.size > 0:
                mims_mask_array[rr, cc] = 1
                mims_pixels_drawn += rr.size
        except Exception as e:
            print(f"Warning: Error rasterizing MIMS shape {i}: {e}")
    print(f"DEBUG: MIMS mask generated with {mims_pixels_drawn} non-zero pixels.")
    # --- End Process MIMS Shapes ---

    # --- Process EM Shapes (Applying Shape-Specific Non-Rotating Transform) ---
    # Mark the calculated target centroid for each shape instead of drawing tiny polygons
    em_pixels_drawn = 0
    output_h, output_w = output_shape  # Get dimensions for bounds checking
    final_em_tform, flip2, max_x_2 = get_points_transform(
        mims_image.image_set, np.array(final_mims_centroids), em_centroids
    )

    final_em_tl = final_em_tform.translation
    final_em_br = final_em_tl + final_em_tform.scale * np.array(output_shape)
    registration_bbox = [final_em_tl.tolist(), final_em_br.tolist()]
    mims_image.save()
    for i, shape in enumerate(em_shapes):  # Iterate through original EM shapes
        if shape.shape[0] < 3:
            # print(f"Skipping EM shape {i}: Not enough vertices ({shape.shape[0]})") # Optional print
            continue

        try:
            translation = final_em_tform.translation
            scale = 1 / final_em_tform.scale
            translated_shape = [
                [s[0] - translation[0], s[1] - translation[1]] for s in shape
            ]
            em_shape = np.array(
                [
                    [np.floor(ts[0] * scale), np.ceil(ts[1] * scale)]
                    for ts in translated_shape
                ]
            )
            rows = np.clip(em_shape[:, 1], 0, output_shape[0] - 1)
            cols = np.clip(em_shape[:, 0], 0, output_shape[1] - 1)
            rr, cc = polygon(rows, cols, output_shape)
            if rr.size > 0:
                em_mask_array[rr, cc] = 1
                em_pixels_drawn += rr.size
        except ValueError as e:  # Catch centroid calculation errors specifically
            print(
                f"Warning: Skipping EM shape {i} due to centroid calculation error: {e}"
            )

    # --- End Process EM Shapes ---

    # --- Save Masks ---
    # (Save mask code omitted for brevity, same as before)
    em_mask_path = reg_loc / "em_mask_for_unwarp.tiff"
    mims_mask_path = reg_loc / "mims_mask_for_unwarp.tiff"
    try:
        print(f"Saving EM mask ({output_shape}) to {em_mask_path}")
        tifffile.imwrite(
            em_mask_path,
            (em_mask_array * 255).astype(np.uint8),
            photometric="minisblack",
        )
        if em_pixels_drawn == 0:
            print("WARNING: EM mask is empty.")

        print(f"Saving MIMS mask ({output_shape}) to {mims_mask_path}")
        tifffile.imwrite(
            mims_mask_path,
            (mims_mask_array * 255).astype(np.uint8),
            photometric="minisblack",
        )
        if mims_pixels_drawn == 0:
            print("WARNING: MIMS mask is empty.")
    except Exception as e:
        raise IOError(f"Error writing mask TIFF files: {e}") from e

    # --- B-Spline ---
    end_time_total = time.time()
    print(
        f"Mask generation finished. Total time before B-spline: {end_time_total - start_time:.2f} seconds."
    )

    # Do B-spline registration
    print("Starting B-spline transform calculation...")
    make_unwarp_transform(mims_image)  # Assumes this uses the saved masks
    print("Starting B-spline image warping...")
    make_unwarp_images(
        mims_image,
        registration_bbox=registration_bbox,
    )  # Assumes this reads warped isotope images & applies B-spline
    mims_image.status = "DEWARPED_ALIGNED"
    mims_image.save()
    print("--- Registration Process Completed Successfully ---")

    if last_output_filepath:
        return str(last_output_filepath)
    else:
        print("Warning: No isotope images were successfully warped.")
        return None
