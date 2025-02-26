import numpy as np
from skimage.transform import estimate_transform
from PIL import Image
import math
from mims.services.image_utils import image_from_im_file
from mims.model_utils import (
    get_concatenated_image,
    load_images_and_bboxes,
)
import cv2
from PIL import ImageOps
import time
from skimage.draw import polygon


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
        mims_pt = rotate_and_flip_point(
            mims_pt, rotation_degrees, composite_image, expanded_composite_image, flip
        )
        mims_pt = [p * scale for p in mims_pt]
        y_translations += [em_pt[1] - mims_pt[1]]
        x_translations += [em_pt[0] - mims_pt[0]]

    x_trans = sum(x_translations) / len(x_translations)
    y_trans = sum(y_translations) / len(y_translations)
    return [y_trans, x_trans]


def get_points_transform(mims_imageviewset, mims_points, em_points):
    tform_no_flip = estimate_transform("similarity", mims_points, em_points)
    error_no_flip = calculate_transformation_error(
        tform_no_flip, mims_points, em_points
    )
    ims, bboxes = load_images_and_bboxes(mims_imageviewset, "SE", flip=True)
    max_x = np.max([pos[0] for bbox in bboxes for pos in bbox])

    # Scenario 2: Flip the MIMS points horizontally (flip x-coordinates)
    mims_points_flipped = mims_points.copy()
    mims_points_flipped[:, 0] = -mims_points_flipped[:, 0]  # Flip x-coordinates
    # Shift all x-coordinates to ensure they are positive
    mims_points_flipped[:, 0] += abs(max_x)

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
    return selected_tform, flip


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

    transform, flip = get_points_transform(mims_imageviewset, mims_points, em_points)

    # Extract transformation parameters
    scale = transform.scale
    rotation_radians = transform.rotation
    rotation_degrees = -np.degrees(rotation_radians)
    translation = transform.translation

    if rotation_degrees < 0:
        rotation_degrees += 360

    ims, bboxes = load_images_and_bboxes(mims_imageviewset, isotope, flip=flip)
    min_x = np.min([pos[0] for bbox in bboxes for pos in bbox])
    min_y = np.min([pos[1] for bbox in bboxes for pos in bbox])
    max_x = np.max([pos[0] for bbox in bboxes for pos in bbox])
    max_y = np.max([pos[1] for bbox in bboxes for pos in bbox])
    bbox = np.array([[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]])
    transformed_bbox = transform(bbox)

    mims_imageviewset.flip = flip
    mims_imageviewset.rotation_degrees = (
        rotation_degrees if flip else 360 - rotation_degrees
    )
    mims_imageviewset.canvas_bbox = transformed_bbox.tolist()
    mims_imageviewset.pixel_size_nm = (
        mims_imageviewset.canvas.pixel_size_nm or 5
    ) * scale

    print(
        f"Scaled by {scale}, rotated by {rotation_degrees}, flipped: {flip}, translated by {translation}"
    )
    mims_imageviewset.save()

    calculate_individual_mims_translations(mims_imageviewset, isotope, transform, flip)
    return


def largest_inner_square(side_length, angle):
    """Calculate the largest possible inner square side length for a given rotation angle."""
    # Convert angle to radians
    return side_length / (
        abs(math.cos(math.radians(angle))) + abs(math.sin(math.radians(angle)))
    )


def calculate_individual_mims_translations(
    mims_imageviewset, isotope, transform_matrix, flip=False
):
    mims_images = mims_imageviewset.mims_images.all()

    # Load the aggregate positions and dimensions of the ROI
    ims, bboxes = load_images_and_bboxes(mims_imageviewset, isotope, flip)
    em_img = np.array(Image.open(mims_imageviewset.canvas.images.first().file.path))
    em_shape = em_img.shape

    for mims_image in mims_images:
        mims_image.flip = flip
        mims_image.rotation_degrees = mims_imageviewset.rotation_degrees
        mims_image.pixel_size_nm = mims_imageviewset.pixel_size_nm

        filename = mims_image.file.name.split("/")[-1].split(".")[0]
        roi = filename.split("_")[-1]

        # Define the ROI corners in the local coordinate space
        corners = np.array(bboxes[int(roi) - 1])

        transformed_corners = transform_matrix(corners)

        min_x = int(np.min(transformed_corners[:, 0]))
        min_y = int(np.min(transformed_corners[:, 1]))
        max_x = int(np.max(transformed_corners[:, 0])) + 1
        max_y = int(np.max(transformed_corners[:, 1])) + 1
        mims_image.canvas_bbox = transformed_corners.tolist()

        if max_x < 0 or min_x > em_shape[1] or max_y < 0 or min_y > em_shape[0]:
            mims_image.status = "OUTSIDE_CANVAS"
            mims_image.save()
            continue

        # Crop the em_img to the bounding box
        cropped_em_img = em_img[max(0, min_y) : max_y, max(0, min_x) : max_x]
        print(f"Roi {roi}: {cropped_em_img.shape}, {min_x}, {min_y}, {max_x}, {max_y}")

        # Adjust the transformed corners to the cropped image coordinates
        adjusted_corners = transformed_corners - [max(0, min_x), max(0, min_y)]

        # Create a mask for the transformed polygon within the cropped region
        mask = np.zeros(cropped_em_img.shape[:2], dtype=np.uint8)
        rr, cc = polygon(adjusted_corners[:, 1], adjusted_corners[:, 0], mask.shape)
        mask[rr, cc] = 1

        # Use the mask to calculate the maximum value inside the polygon
        # Ensure that the mask is correctly applied
        masked_values = cropped_em_img[mask == 1]
        if masked_values.size == 0:
            em_max_val = 0
        else:
            em_max_val = np.max(masked_values)

        if em_max_val == 0:
            mims_image.status = "OUTSIDE_CANVAS"
            mims_image.save()
            continue

        mims_image.status = "NEED_USER_ALIGNMENT"
        mims_image.save()


def calculate_individual_mims_translations2(mims_imageviewset, isotope):
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
    if flip:
        composite_image = composite_image.transpose(Image.FLIP_LEFT_RIGHT)
    composite_image = composite_image.rotate(-rotation_degrees, expand=True)
    composite_image = np.array(composite_image)
    em_image_obj = mims_imageviewset.canvas.images.first()
    scale = mims_imageviewset.pixel_size_nm / em_image_obj.pixel_size_nm
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
        if "ROI_12" not in filename:
            continue
        roi = filename.split("_")[-1]
        print(roi, "time1", time.time() - start)
        im, bboxes = load_images_and_bboxes(mims_imageviewset, isotope)
        positions = [bbox[0] for bbox in bboxes]
        # Load the MIMS image for the isotope and load as PIL image
        img_orig = image_from_im_file(mims_image.file.path, isotope, True)
        img_orig = Image.fromarray(img_orig)
        if isotope == "32S":
            img_orig = ImageOps.invert(img_orig)
        img = img_orig.copy()
        # Apply the flip and rotation if necessary to it
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        img = img.rotate(-rotation_degrees, expand=True)
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
        print(
            "loc",
            max_val,
            scale,
            mims_imageviewset.canvas_y,
            mims_imageviewset.canvas_x,
            max_loc,
        )
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
            print("Out of bounds: ", approx_em_loc, em_orig_shape, mims_scaled_shape)
            mims_image.status = "OUTSIDE_CANVAS"
            mims_image.save()
            continue
        print("Seems in bounds:", approx_em_loc, em_orig_shape, mims_scaled_shape)
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
