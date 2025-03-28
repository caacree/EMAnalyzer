import numpy as np
import pyvips
from skimage import transform, exposure
import re
from pystackreg import StackReg
from pystackreg.util import to_uint16
import sims
from scipy import ndimage
from PIL import Image

possible_12c_names = ["12C", "12C2"]
possible_13c_names = ["13C", "12C 13C"]
possible_15n_names = ["15N 12C", "12C 15N"]
possible_14n_names = ["14N 12C", "12C 14N"]


def manipulate_image(image, angle, flip_hor):
    manipulated_image = pyvips.Image.new_from_array(image)
    if angle:
        manipulated_image = manipulated_image.rotate(angle, background=0)
    if flip_hor:
        manipulated_image = manipulated_image.fliphor()
    return manipulated_image.numpy()


def update_top_locations(top_locations, x, y, iou, angle, flip_hor):
    to_add = (x, y, iou, angle, flip_hor)
    # Check if this (x, y) should be added to top_locations
    if len(top_locations) < 3:
        top_locations.append(to_add)
        return top_locations

    min_iou = min([i[2] for i in top_locations])
    if iou < min_iou and len(top_locations) >= 3:
        return top_locations

    for i, (tx, ty, tiou, tangle, tflip_hor) in enumerate(top_locations):
        distance = np.sqrt((tx - x) ** 2 + (ty - y) ** 2)
        if distance < 40 and tflip_hor is flip_hor and abs(tangle - angle) < 30:
            if iou > tiou:
                top_locations[i] = to_add
                top_locations = sorted(top_locations, key=lambda x: x[2], reverse=True)[
                    :3
                ]
                return top_locations

    if iou > min_iou:
        top_locations.append(to_add)
        # Reorder by iou and remove the lowest
    top_locations = sorted(top_locations, key=lambda x: x[2], reverse=True)[:3]
    return top_locations


def extract_final_digit(filename):
    # Regular expression to find the final number before the .im extension
    match = re.search(r"(\d+)(?=\.im$)", filename)
    return (
        int(match.group(0)) if match else float("inf")
    )  # If no match, assign infinity for last sorting


def do_sliding_search(im1, im2, valid_im1, valid_im2, angle, flip_hor):
    best_locations = []
    # Do a sliding search for im2 in im1
    for y in range(0, im1.shape[0] - im2.shape[0], 20):
        for x in range(0, im1.shape[1] - im2.shape[1], 20):
            im1_slice = im1[y : y + im2.shape[0], x : x + im2.shape[1]]
            if im1_slice.shape != im2.shape:
                print("this shouldnt happen", im1_slice.shape, im2.shape)
                continue
            valid_im1_slice = valid_im1[y : y + im2.shape[0], x : x + im2.shape[1]]
            valid_mask = valid_im1_slice & valid_im2
            intersection = np.logical_and(im1_slice, im2).sum()
            union = (
                np.logical_and(valid_mask, np.logical_or(im1_slice, im2))
                .astype(np.uint8)
                .sum()
            )
            if (
                valid_mask.sum() < 100000
                or union < 2000
                or (intersection / valid_mask.sum()) > 0.8
            ):
                # Should have at least 1,000,000 valid pixels and 2000 union
                continue
            iou = 0
            if union:
                iou = intersection / union
                best_locations = update_top_locations(
                    best_locations, x, y, iou, angle, flip_hor
                )
    return best_locations


def non_zero_percentile(arr, percentile):
    """
    Calculate the percentile for all non-zero values in the given array.

    Parameters:
    arr (numpy.ndarray): Input array.
    percentile (float): Percentile to compute (0-100).

    Returns:
    float: The percentile value of the non-zero elements.
    """
    # Filter out the non-zero values
    non_zero_values = arr[arr != 0]

    # Calculate the percentile of the non-zero values
    percentile_value = np.percentile(non_zero_values, percentile)

    return percentile_value


def correct_inner_zeros(original_array):
    array = original_array.astype(np.uint8)
    # Correct the inner zeros to 1s
    # First set all 0s to 1s, then outer 1s to 0s
    # 1. Set all 0s to 1s
    array = np.where(array == 0, 1, array)
    # 2. Set outer 1s to 0s
    for y in range(0, array.shape[0] - 1):
        # left side
        for x in range(0, array.shape[1] - 1):
            value = array[y][x]
            if value not in [1]:
                break
            array[y][x] = 0
        # right side
        for x in range(array.shape[1] - 1, 0, -1):
            value = array[y][x]
            if value not in [1]:
                break
            array[y][x] = 0

    for x in range(0, array.shape[1] - 1):
        # top side
        for y in range(0, array.shape[0] - 1):
            value = array[y][x]
            if value not in [1]:
                break
            array[y][x] = 0
        # bottom side
        for y in range(array.shape[0] - 1, 0, -1):
            value = array[y][x]
            if value not in [1]:
                break
            array[y][x] = 0
    return array


def calculate_affine_matrix(points1, points2):
    """Calculate the affine transformation matrix to align points2 to points1."""
    matrix, _ = transform.estimate_transform("affine", points2, points1)
    return matrix


def decompose_affine_matrix(matrix):
    """
    Decompose the affine transformation matrix into translation, rotation, and flip.

    Args:
        matrix: 3x3 affine transformation matrix.

    Returns:
        translation: Tuple of (tx, ty).
        rotation: Angle of rotation in degrees.
        flip: Boolean indicating if a horizontal flip was applied.
    """
    # Extract the rotation and scaling part of the matrix
    R = matrix.params[:2, :2]
    # Calculate the determinant to check for flip
    det = np.linalg.det(R)
    flip = det < 0

    if flip:
        # Reflect the rotation matrix to handle the flip
        R[:, 0] = -R[:, 0]

    # Calculate rotation angle in radians
    rotation_rad = np.arctan2(R[1, 0], R[0, 0])
    rotation_deg = np.degrees(rotation_rad)

    # Extract the translation part of the matrix
    tx, ty = matrix.params[:2, 2]

    return (tx, ty), rotation_deg, flip


def find_transformation(image1_path, image2_path, points1, points2):
    """
    Find the transformation parameters to align the second image to the first image based on given landmark points.

    Args:
        image1_path: Path to the first image.
        image2_path: Path to the second image.
        points1: List of (x, y) tuples representing landmark points in the first image.
        points2: List of (x, y) tuples representing landmark points in the second image.

    Returns:
        translation: Tuple of (tx, ty).
        rotation: Angle of rotation in degrees.
        flip: Boolean indicating if a horizontal flip was applied.
    """
    # Convert points to numpy arrays
    points1 = np.array(points1)
    points2 = np.array(points2)

    # Calculate affine transformation matrix
    matrix = calculate_affine_matrix(points1, points2)

    # Decompose the affine transformation matrix
    translation, rotation, flip = decompose_affine_matrix(matrix)

    return translation, rotation, flip


def image_from_im_file(im_file, species, autocontrast=False):
    """
    Extract image data for a specific species from an .im file

    Args:
        im_file (str): Path to the .im file
        species (str): Name of the species/isotope to extract
        autocontrast (bool): Whether to apply autocontrast scaling

    Returns:
        numpy.ndarray: Image data as a numpy array
    """
    mims = sims.SIMS(im_file)
    if not mims or mims.data is None or mims.data.species is None:
        raise ValueError("Invalid .im file")

    def get_species_summed(mims, species):
        # Extract and register the isotope image
        sr = StackReg(StackReg.AFFINE)
        sr.register_stack(mims.data.loc[species].to_numpy(), reference="previous")
        stacked = sr.transform_stack(mims.data.loc[species].to_numpy())
        stacked = to_uint16(stacked)
        species_summed = stacked.sum(axis=0)
        species_summed = ndimage.median_filter(species_summed, size=1).astype(np.uint16)
        return species_summed

    species_summed = None
    if species in mims.data.species.values:
        species_summed = get_species_summed(mims, species)
    elif species == "15N14N_ratio":
        n15 = next(
            (name for name in possible_15n_names if name in mims.data.species.values),
            None,
        )
        n14 = next(
            (name for name in possible_14n_names if name in mims.data.species.values),
            None,
        )
        if n15 and n14:
            n15 = get_species_summed(mims, n15)
            n14 = get_species_summed(mims, n14)
            n14[n14 == 0] = 1
            species_summed = np.divide(n15, n14) * 10000
        else:
            raise ValueError(f"Species {species} not found in .im file")
    elif species == "13C12C_ratio":
        c13 = next(
            (name for name in possible_13c_names if name in mims.data.species.values),
            None,
        )
        c12 = next(
            (name for name in possible_12c_names if name in mims.data.species.values),
            None,
        )
        if c13 and c12:
            print(c13, c12)
            c13 = get_species_summed(mims, c13)
            c12 = get_species_summed(mims, c12)
            c12[c12 == 0] = 1
            species_summed = np.divide(c13, c12) * 10000
        else:
            raise ValueError(f"Species {species} not found in .im file")

    if autocontrast:
        vmin, vmax = np.percentile(species_summed, (1, 99))
        species_summed = exposure.rescale_intensity(
            species_summed, in_range=(vmin, vmax), out_range=(0, 255)
        ).astype(np.uint8)

    return species_summed


# Example usage:
# image1_path = 'path_to_first_image.png'
# image2_path = 'path_to_second_image.png'
# points1 = [(x1, y1), (x2, y2), (x3, y3)]  # Example landmark points in the first image
# points2 = [(u1, v1), (u2, v2), (u3, v3)]  # Corresponding points in the second image

# translation, rotation, flip = find_transformation(image1_path, image2_path, points1, points2)
# print(f"Translation: {translation}")
# print(f"Rotation: {rotation} degrees")
# print(f"Horizontal flip: {flip}")
