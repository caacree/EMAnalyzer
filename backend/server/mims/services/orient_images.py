import numpy as np
from skimage.transform import estimate_transform
import sims


def calculate_transformation_error(tform, src_points, dst_points):
    # Apply the transformation to the source points
    transformed_points = tform(src_points)
    # Calculate the error as the sum of squared differences
    error = np.sum((transformed_points - dst_points) ** 2)
    return error


def orient_viewset(mims_imageviewset, points):
    # This function takes a MIMSImageViewSet object and a list of points as input.
    # The points are in the format of
    # {
    #   "em": [{x: x1, y: y1}, {x: x2, y: y2}, {x: x3, y: y3}],
    #   "mims": [{x: x1, y: y1}, {x: x2, y: y2}, {x: x3, y: y3}]
    # }
    # It then calculates the rotation and flip needed to align the MIMS image to the EM image,
    # as well as the scale needed to match the pixel size of the MIMS image to the EM image and
    # the translation needed to align the MIMS image to the EM image.
    em_points = np.array([[point["y"], point["x"]] for point in points["em"]])
    mims_points = np.array([[point["y"], point["x"]] for point in points["mims"]])
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
    scale = np.sqrt(selected_tform.params[0, 0] ** 2 + selected_tform.params[1, 0] ** 2)
    rotation_radians = np.arctan2(
        selected_tform.params[1, 0], selected_tform.params[0, 0]
    )
    rotation_degrees = np.degrees(rotation_radians)
    translation = selected_tform.params[:2, 2]
    print(selected_tform.params)
    print("rotation_degrees", flip, rotation_degrees, translation, scale)

    mims_imageviewset.flip = flip
    mims_imageviewset.rotation_degrees = rotation_degrees
    mims_imageviewset.em_coordinates_x = translation[0]
    mims_imageviewset.em_coordinates_y = translation[1]
    mims_imageviewset.em_scale = scale
    mims_imageviewset.save()
    # calculate_individual_mims_translations(mims_imageviewset)
    return


def calculate_individual_mims_translations(mims_imageviewset):
    mims_images = mims_imageviewset.mims_images.all()
    # Get transformation parameters
    flip = mims_imageviewset.flip
    rotation_degrees = mims_imageviewset.rotation_degrees
    composite_translation = np.array(
        [mims_imageviewset.em_coordinates_x, mims_imageviewset.em_coordinates_y]
    )
    scale = mims_imageviewset.em_scale

    # Convert rotation to radians
    rotation_radians = np.radians(rotation_degrees)

    # Create rotation matrix
    rotation_matrix = np.array(
        [
            [np.cos(rotation_radians), -np.sin(rotation_radians)],
            [np.sin(rotation_radians), np.cos(rotation_radians)],
        ]
    )

    # Get reference point (e.g., top-left corner of the composite image)
    mims_meta = sims.SIMS(mims_images[0].file.path).header["Image"]
    mims_pixel_size = mims_meta["raster"] / mims_meta["width"]

    min_x = min(im.header["sample x"] for im in mims_images)
    max_y = max(im.header["sample y"] for im in mims_images)
    reference_point = np.array([min_x, max_y])

    # Calculate and store translations for each MIMS image
    for mims_image in mims_images:
        # Get image position
        x, y = mims_image.header["sample x"], mims_image.header["sample y"]
        position = np.array([x, y])

        # Calculate relative position to reference point
        relative_position = (position - reference_point) * 1000 / mims_pixel_size

        # Apply flip if necessary
        if flip:
            relative_position[0] = -relative_position[0]

        # Apply rotation and scaling
        transformed_position = scale * rotation_matrix.dot(relative_position)

        # Calculate final translation
        translation = composite_translation + transformed_position

        # Store the translation for this MIMS image
        mims_image.em_coordinates_x = translation[0]
        mims_image.em_coordinates_y = translation[1]
        mims_image.save()

    return
