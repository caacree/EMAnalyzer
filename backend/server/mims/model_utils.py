import numpy as np
import os
import sims
from PIL import Image
import pprint
from pathlib import Path
import sims
import os
from pathlib import Path
import sims


# Function to get autocontrast image path
def get_autocontrast_image_path(mims_image, species):
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
def load_images_and_bboxes(
    mims_image_set,
    species="32S",
    flip=False,
):
    mims_images = list(mims_image_set.mims_images.all().order_by("image_set_priority"))

    images = []
    bboxes = []
    tl_corners = []
    mims_pixel_size = None

    for mims in mims_images:
        im = sims.SIMS(mims.file.path)
        if not mims_pixel_size:
            mims_meta = im.header["Image"]
            mims_pixel_size = mims_meta["raster"] / mims_meta["width"]

        x, y = im.header["sample x"], im.header["sample y"]
        x, y = y, x
        # Initial tl_corners are in sample coordinates (microns)
        tl_corners.append((x, y))
    min_tl_x = np.min([pos[0] for pos in tl_corners])
    max_tl_y = np.max([pos[1] for pos in tl_corners])
    # Convert tl_corners to image coordinates (microns)
    tl_corners = [(pos[0] - min_tl_x, max_tl_y - pos[1]) for pos in tl_corners]
    # Convert tl_corners to image coordinates (pixels)
    tl_corners = [
        [int(pos[0] * 1000 / mims_pixel_size), int(pos[1] * 1000 / mims_pixel_size)]
        for pos in tl_corners
    ]

    for idx, mims in enumerate(mims_images):
        autocontrast_path = get_autocontrast_image_path(mims, species)
        if os.path.exists(autocontrast_path):
            image = Image.open(autocontrast_path)
            if flip:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            images.append(np.array(image))
            width = image.width
            height = image.height
            bbox = np.array(
                [
                    tl_corners[idx],
                    [tl_corners[idx][0] + width, tl_corners[idx][1]],
                    [tl_corners[idx][0] + width, tl_corners[idx][1] + height],
                    [tl_corners[idx][0], tl_corners[idx][1] + height],
                ]
            )
            bboxes.append(bbox)
    if flip:  # flip x-coordinates
        for bbox in bboxes:
            bbox[:, 0] = -bbox[:, 0]
        min_x = np.min([pos[0] for bbox in bboxes for pos in bbox])
        # Shift all x-coordinates to ensure they are positive
        for i, bbox in enumerate(bboxes):
            bbox[:, 0] += abs(min_x)
            # And then re-arrange the corners
            bboxes[i] = np.array(
                [
                    bbox[1],
                    bbox[0],
                    bbox[3],
                    bbox[2],
                ]
            )
    return images, bboxes


# Function to create and display the concatenated image
def get_concatenated_image(mims_image_set, species, flip=False):
    images, bboxes = load_images_and_bboxes(mims_image_set, species, flip)
    positions = [bbox[0] for bbox in bboxes]
    mims_meta = sims.SIMS(mims_image_set.mims_images.first().file.path).header["Image"]
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

    canvas_width = int((max_x - min_x) + image_width)
    canvas_height = int((max_y - min_y) + image_height)
    print(
        min_x,
        min_y,
        max_x,
        max_y,
        mims_pixel_size,
        image_width,
        image_height,
        canvas_width,
        canvas_height,
    )

    canvas = np.zeros((canvas_height, canvas_width), dtype=np.uint8)

    # Place each image on the canvas
    for idx, img in enumerate(images):
        x_offset, y_offset = positions[idx]
        canvas[
            y_offset : y_offset + image_height, x_offset : x_offset + image_width
        ] = img

    return canvas
