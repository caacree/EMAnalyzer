import numpy as np
from skimage.transform import estimate_transform
import sims
from PIL import Image
import math
from mims.model_utils import (
    get_concatenated_image,
    get_autocontrast_image_path,
)
import cv2
from PIL import ImageOps
import time


def calculate_transformation_error(tform, src_points, dst_points):
    # Apply the transformation to the source points
    transformed_points = tform(src_points)
    # Calculate the error as the sum of squared differences
    error = np.sum((transformed_points - dst_points) ** 2)
    return error


def rotate_and_flip_point(
    point, angle, original_image, rotated_image, flip_horizontal=False
):
    x0, y0 = point
    # Original image center
    cx, cy = original_image.width / 2.0, original_image.height / 2.0
    # Rotated image center
    new_cx, new_cy = rotated_image.width / 2.0, rotated_image.height / 2.0

    # Convert angle to radians
    angle_rad = math.radians(angle)

    # Adjust coordinates to center
    x_rel = x0 - cx
    y_rel = y0 - cy

    # Invert y-axis for image coordinate system
    y_rel = -y_rel

    # Apply rotation matrix
    x_rot = x_rel * math.cos(angle_rad) - y_rel * math.sin(angle_rad)
    y_rot = x_rel * math.sin(angle_rad) + y_rel * math.cos(angle_rad)

    # Invert y-axis back
    y_rot = -y_rot

    # Translate back to image coordinates
    x_new = x_rot + new_cx
    y_new = y_rot + new_cy

    # Handle horizontal flip
    if flip_horizontal:
        x_new = rotated_image.width - x_new

    return [x_new, y_new]


def calculate_translations(
    mims_points, em_points, composite_image, rotation_degrees, flip, scale
):
    expanded_composite_image = composite_image.rotate(rotation_degrees, expand=True)

    x_translations = []
    y_translations = []
    for i in range(len(mims_points)):
        mims_pt = mims_points[i]
        em_pt = em_points[i]
        # 1. Rotate, then flip, then scale and see the translation from the EM point
        print("1", mims_pt, rotation_degrees, flip)
        mims_pt = rotate_and_flip_point(
            mims_pt, rotation_degrees, composite_image, expanded_composite_image, flip
        )
        print("2", mims_pt)
        mims_pt = [p * scale for p in mims_pt]
        y_translations += [em_pt[1] - mims_pt[1]]
        x_translations += [em_pt[0] - mims_pt[0]]

    print(f"X translations: {x_translations}, Y translations: {y_translations}")
    x_trans = sum(x_translations) / len(x_translations)
    y_trans = sum(y_translations) / len(y_translations)
    return [y_trans, x_trans]


def orient_viewset(mims_imageviewset, points, isotope):
    # This function takes a MIMSImageViewSet object and a list of points as input.
    # The points are in the format of
    # {
    #   "em": [{x: x1, y: y1}, {x: x2, y: y2}, {x: x3, y: y3}],
    #   "mims": [{x: x1, y: y1}, {x: x2, y: y2}, {x: x3, y: y3}]
    # }
    # It then calculates the rotation and flip needed to align the MIMS image to the EM image,
    # as well as the scale needed to match the pixel size of the MIMS image to the EM image and
    # the translation needed to align the MIMS image to the EM image.
    em_points = np.array([[point["x"], point["y"]] for point in points["em"]])
    mims_points = np.array([[point["x"], point["y"]] for point in points["mims"]])

    tform_no_flip = estimate_transform("similarity", mims_points, em_points)
    error_no_flip = calculate_transformation_error(
        tform_no_flip, mims_points, em_points
    )

    # Scenario 2: Flip the MIMS points horizontally (flip x-coordinates)
    mims_points_flipped = mims_points.copy()
    mims_points_flipped[:, 1] = -mims_points_flipped[:, 1]  # Flip x-coordinates

    tform_with_flip = estimate_transform("similarity", mims_points_flipped, em_points)
    error_with_flip = calculate_transformation_error(
        tform_with_flip, mims_points_flipped, em_points
    )

    if error_with_flip < error_no_flip:
        selected_tform = tform_with_flip
        flip = True
    else:
        selected_tform = tform_no_flip
        flip = False

    # Extract transformation parameters
    scale = selected_tform.scale
    rotation_radians = selected_tform.rotation
    rotation_degrees = np.degrees(rotation_radians)
    if rotation_degrees < 0:
        rotation_degrees += 360

    print(f"Rotation: {rotation_degrees}, Flip: {flip}, Scale: {scale}")

    # Get translation in coordinates the way we will calculate them in the rest of the app
    composite_image = Image.fromarray(get_concatenated_image(mims_imageviewset, "32S"))
    translation = calculate_translations(
        mims_points, em_points, composite_image, rotation_degrees, flip, scale
    )

    mims_imageviewset.flip = flip
    mims_imageviewset.rotation_degrees = rotation_degrees
    mims_imageviewset.canvas_x = translation[1]
    mims_imageviewset.canvas_y = translation[0]
    mims_imageviewset.pixel_size_nm = (
        mims_imageviewset.canvas.pixel_size_nm or 5
    ) * scale
    print(f"Scaled by {scale}, rotated by {rotation_degrees}, flipped: {flip}")
    mims_imageviewset.save()

    calculate_individual_mims_translations(mims_imageviewset, isotope)
    return


def largest_inner_square(side_length, angle):
    """Calculate the largest possible inner square side length for a given rotation angle."""
    # Convert angle to radians
    return side_length / (
        abs(math.cos(math.radians(angle))) + abs(math.sin(math.radians(angle)))
    )


def calculate_individual_mims_translations(mims_imageviewset, isotope):
    start = time.time()
    # Print seconds elapsed
    mims_images = mims_imageviewset.mims_images.all()
    # Get transformation parameters
    flip = mims_imageviewset.flip
    rotation_degrees = mims_imageviewset.rotation_degrees
    composite_image = Image.fromarray(
        get_concatenated_image(mims_imageviewset, isotope)
    )
    if isotope == "32S":
        composite_image = ImageOps.invert(composite_image)
    composite_image = composite_image.rotate(-rotation_degrees, expand=True)
    if flip:
        composite_image = composite_image.transpose(Image.FLIP_LEFT_RIGHT)
    composite_image = np.array(composite_image)
    em_image_obj = mims_imageviewset.canvas.images.first()
    scale = mims_imageviewset.pixel_size_nm / (em_image_obj.pixel_size_nm or 5)
    # Load the EM image as a numpy array
    em_image = Image.open(em_image_obj.file.path)
    em_image_array = np.array(em_image)
    scaled_em = cv2.resize(
        em_image_array,
        (int(em_image_array.shape[1] / scale), int(em_image_array.shape[0] / scale)),
    )
    # Calculate and store translations for each MIMS image
    for mims_image in mims_images:
        filename = mims_image.file.name.split("/")[-1].split(".")[0]
        roi = filename.split("_")[-1]
        print(roi, "time1", time.time() - start)
        # Load the MIMS image for the isotope and load as PIL image
        img_orig = get_autocontrast_image_path(mims_image, isotope)
        img_orig = Image.open(img_orig)
        if isotope == "32S":
            img_orig = ImageOps.invert(img_orig)
        img = img_orig.copy()
        # Apply the flip and rotation if necessary to it
        img = img.rotate(-rotation_degrees, expand=True)
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        img_array = np.array(img)

        # Calculate the center of the image
        center_x, center_y = img_array.shape[1] // 2, img_array.shape[0] // 2

        # Calculate the cropping box
        largest_inner_square_side = int(
            largest_inner_square(img_orig.width, rotation_degrees)
        )
        start_x = center_x - largest_inner_square_side // 2
        start_y = center_y - largest_inner_square_side // 2
        end_x = center_x + largest_inner_square_side // 2
        end_y = center_y + largest_inner_square_side // 2

        # Crop the image to the largest inner square
        cropped_img_array = img_array[start_y:end_y, start_x:end_x]
        orig_cropped_img_array_shape = cropped_img_array.shape

        # Then find the image in the composite image
        result = cv2.matchTemplate(
            composite_image, cropped_img_array, cv2.TM_CCOEFF_NORMED
        )
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        # Now from this approximation, find a closer match in the actual EM image
        # Find the original EM location of the MIMS image
        mims_y = mims_imageviewset.canvas_y + max_loc[1] * scale
        mims_x = mims_imageviewset.canvas_x + max_loc[0] * scale
        mims_scaled_shape = [r * scale for r in np.array(img_orig).shape]
        em_orig_shape = em_image_array.shape
        # Skip if sufficiently far outside of the known EM bounds
        approx_em_loc = [mims_y, mims_x]
        if (
            approx_em_loc[0] < -mims_scaled_shape[0]
            or approx_em_loc[0] > em_orig_shape[0] + mims_scaled_shape[0]
            or approx_em_loc[1] < -mims_scaled_shape[1]
            or approx_em_loc[1] > em_orig_shape[1] + mims_scaled_shape[1]
        ):
            print("Out of bounds: ", approx_em_loc, em_orig_shape)
            mims_image.status = "OUTSIDE_CANVAS"
            mims_image.save()
            continue
        print("Seems in bounds:", approx_em_loc, em_orig_shape)
        # Then scale it down
        mims_y_scaled = mims_y / scale
        mims_x_scaled = mims_x / scale
        crop_size = int(img_array.shape[0] * 1.3)
        amt_to_add_back = crop_size * 0.5
        crop_y_start = max(mims_y_scaled - amt_to_add_back, 0)
        crop_y_end = min(mims_y_scaled + (crop_size * 1.5), scaled_em.shape[0])
        crop_x_start = max(mims_x_scaled - amt_to_add_back, 0)
        crop_x_end = min(mims_x_scaled + (crop_size * 1.5), scaled_em.shape[1])
        scaled_em_crop = scaled_em[
            int(crop_y_start) : int(crop_y_end), int(crop_x_start) : int(crop_x_end)
        ]
        y_size_limit = int(scaled_em.shape[0] - mims_y_scaled)
        if (y_size_limit) < cropped_img_array.shape[0]:
            if crop_y_start == 0:
                cropped_img_array = cropped_img_array[-y_size_limit:, :]
            else:
                cropped_img_array = cropped_img_array[:y_size_limit, :]
        x_size_limit = int(scaled_em.shape[1] - mims_x_scaled)
        if (x_size_limit) < cropped_img_array.shape[1]:
            if crop_x_start == 0:
                cropped_img_array = cropped_img_array[:, -x_size_limit:]
            else:
                cropped_img_array = cropped_img_array[:, :x_size_limit]
        # Now find the MIMS image in the crop
        # These 2 calls take ~0.3 seconds
        if cropped_img_array.shape[0] == 0 or cropped_img_array.shape[1] == 0:
            mims_image.status = "NO_CELLS"
            mims_image.save()
            continue
        result = cv2.matchTemplate(
            scaled_em_crop, cropped_img_array, cv2.TM_CCOEFF_NORMED
        )
        _, _, _, max_loc = cv2.minMaxLoc(result)
        scaled_cropped_em_y_start = max(max_loc[1], 0)
        scaled_em_y_start = int(crop_y_start + scaled_cropped_em_y_start)
        em_y_start = int(scaled_em_y_start * scale)
        scaled_cropped_em_x_start = max(max_loc[0], 0)
        scaled_em_x_start = int(crop_x_start + scaled_cropped_em_x_start)
        em_x_start = int(scaled_em_x_start * scale)

        mims_image.alignments.all().delete()
        mims_image.alignments.create(
            x_offset=em_x_start,
            y_offset=em_y_start,
            flip_hor=flip,
            rotation_degrees=rotation_degrees,
            scale=scale,
            status="GUESS",
        )
        mims_image.status = "NEED_USER_ALIGNMENT"
        mims_image.save()
    return
