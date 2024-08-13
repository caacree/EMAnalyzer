import numpy as np
from skimage.transform import estimate_transform


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
    em_points = np.array([[point["x"], point["y"]] for point in points["em"]])
    mims_points = np.array([[point["x"], point["y"]] for point in points["mims"]])

    tform_no_flip = estimate_transform("similarity", mims_points, em_points)
    error_no_flip = calculate_transformation_error(
        tform_no_flip, mims_points, em_points
    )

    # Scenario 2: Flip the MIMS points horizontally (flip x-coordinates)
    mims_points_flipped = mims_points.copy()
    mims_points_flipped[:, 0] = -mims_points_flipped[:, 0]  # Flip x-coordinates

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

    mims_imageviewset.flip = flip
    mims_imageviewset.rotation_degrees = rotation_degrees
    mims_imageviewset.em_coordinates_x = translation[0]
    mims_imageviewset.em_coordinates_y = translation[1]
    mims_imageviewset.em_scale = scale
    mims_imageviewset.save()
    print(flip, rotation_degrees, translation, scale)
    return
