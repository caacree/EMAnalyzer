from django.conf import settings
import numpy as np
import os
from matplotlib import pyplot as plt
import functools
import math
import sims
import copy
from skimage.measure import regionprops
from scipy import spatial
import pickle
from matplotlib.figure import Figure
import pyvips
from emimage.models import EMImage
from mims.models import MIMSImage, MIMSImageSet
from PIL import Image
from scipy.ndimage import rotate
import pprint
from pathlib import Path
import sims


# Function to get autocontrast image path
def get_autocontrast_image_path(mims_image, species):
    mims_image_set = mims_image.image_set

    isotope_image_dir = os.path.join(
        os.path.dirname(mims_image.file.path),
        mims_image.file.name.split(".")[0].split("/")[-1],
        "isotopes",
    )
    autocontrast_path = os.path.join(isotope_image_dir, f"{species}_autocontrast.png")
    if not Path(autocontrast_path).exists():
        normal_path = os.path.join(isotope_image_dir, f"{species}.png")
        if Path(normal_path).exists():
            autocontrast_path = normal_path
    return autocontrast_path


# Function to load images and their positions
def load_images_and_positions(
    em_image,
    species,
):
    mims_image_set = em_image.mimsimageset_set.first()
    mims_images = list(mims_image_set.mims_images.all())

    images = []
    positions = []

    for mims in mims_images:
        im = sims.SIMS(mims.file.path)
        with open("./sims_header.txt", "w") as f:
            pprint.pprint(im.header, f)
        x, y = im.header["sample x"], im.header["sample y"]
        x, y = y, x

        autocontrast_path = get_autocontrast_image_path(mims, species)
        if os.path.exists(autocontrast_path):
            image = Image.open(autocontrast_path)
            images.append(np.array(image))
            positions.append((x, y))

    return images, positions


# Function to create and display the concatenated image
def get_concatenated_image(em_image, species, rotation_angle=None, flip=False):
    images, positions = load_images_and_positions(em_image, species)
    mims_meta = sims.SIMS(
        em_image.mimsimageset_set.first().mims_images.first().file.path
    ).header["Image"]
    mims_pixel_size = mims_meta["raster"] / mims_meta["width"]

    if not images:
        print("No images found for the given species.")
        return

    # Assuming all images are the same size
    image_height, image_width = images[0].shape

    # Determine the extent of the concatenated image
    min_x = min(pos[0] for pos in positions)
    min_y = min(pos[1] for pos in positions)
    max_x = max(pos[0] for pos in positions)
    max_y = max(pos[1] for pos in positions)

    canvas_width = int((max_x - min_x) * 1000 / mims_pixel_size + image_width)
    canvas_height = int((max_y - min_y) * 1000 / mims_pixel_size + image_height)

    # Create a blank canvas
    canvas = np.zeros((canvas_height, canvas_width), dtype=np.uint8)

    # Place each image on the canvas
    for img, (x, y) in zip(images, positions):
        x_offset = int((x - min_x) * 1000 / mims_pixel_size)
        y_offset = int((max_y - y) * 1000 / mims_pixel_size)
        canvas[
            y_offset : y_offset + image_height, x_offset : x_offset + image_width
        ] = img

    return canvas
