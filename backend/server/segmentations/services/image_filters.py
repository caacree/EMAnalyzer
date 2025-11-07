"""Image filtering and loading utilities."""

import logging
import traceback

import numpy as np
import tifffile
from PIL import Image
from skimage import filters

logger = logging.getLogger(__name__)


def load_tiff_file(file_path: str) -> np.ndarray:
    """Load a TIFF or PNG file and return as numpy array.

    Note: This is primarily used to load the compressed PNG files we save,
    but can also handle TIFF files.
    """
    try:
        # Check file extension
        if file_path.lower().endswith(".png"):
            # Load PNG with PIL
            image = np.array(Image.open(file_path))
        else:
            # Try tifffile first for TIFF files (better for scientific TIFFs)
            try:
                image = tifffile.imread(file_path)
            except:
                # Fallback to PIL for TIFF
                image = np.array(Image.open(file_path))

    except Exception as e:
        logger.error(f"Error loading image file: {str(e)}")
        raise

    # Ensure 2D image
    if len(image.shape) > 2:
        # Take first channel if multi-channel (handle RGBA, RGB, etc.)
        if image.shape[-1] == 4:  # RGBA
            # For RGBA, use alpha channel if it has meaningful data, otherwise use first channel
            alpha = image[..., 3]
            if np.any(alpha != 255):  # Alpha channel has data
                image = alpha
            else:
                image = image[..., 0]
        elif image.shape[-1] == 3:  # RGB
            # Convert RGB to grayscale if needed
            image = np.mean(image, axis=-1).astype(image.dtype)
        else:
            # Take first channel for other multi-channel images
            image = image[..., 0] if image.shape[-1] < image.shape[0] else image[0]

    return image


def apply_sobel_filter(image_array: np.ndarray) -> np.ndarray:
    """
    Apply Sobel edge detection filter to an image.

    For large images (>10000 pixels on any side), uses pyvips for memory-efficient
    streaming processing. For smaller images, uses scikit-image.

    Args:
        image_array: Input image as numpy array (grayscale uint8)

    Returns:
        Edge magnitude image as uint8 (0-255)
    """
    import pyvips

    try:
        # Ensure 2D image
        if len(image_array.shape) > 2:
            image_array = (
                image_array[:, :, 0] if image_array.shape[-1] <= 4 else image_array[0]
            )

        height, width = image_array.shape
        logger.info(f"Applying Sobel filter to {width}x{height} image")

        # For very large images, use pyvips for memory efficiency
        if width > 10000 or height > 10000:
            logger.info("Using pyvips streaming Sobel for large image")

            # Convert numpy array to pyvips image
            img = pyvips.Image.new_from_memory(
                image_array.tobytes(), width, height, bands=1, format="uchar"
            )

            # Apply Sobel operator using pyvips convolution
            # Sobel X kernel
            sobel_x = pyvips.Image.new_from_array(
                [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], scale=1
            )

            # Sobel Y kernel
            sobel_y = pyvips.Image.new_from_array(
                [[-1, -2, -1], [0, 0, 0], [1, 2, 1]], scale=1
            )

            # Convolve with both kernels
            grad_x = img.conv(sobel_x)
            grad_y = img.conv(sobel_y)

            # Compute magnitude: sqrt(gx^2 + gy^2)
            # Use ** operator for power in pyvips
            magnitude = (grad_x * grad_x + grad_y * grad_y) ** 0.5

            # Normalize to 0-255 uint8
            max_val = magnitude.max()
            if max_val > 0:
                magnitude = magnitude / max_val * 255

            magnitude = magnitude.cast("uchar")

            # Convert back to numpy array
            edges = np.frombuffer(magnitude.write_to_memory(), dtype=np.uint8).reshape(
                height, width
            )

            logger.info("Sobel filter complete (pyvips mode)")
            return edges

        else:
            # For smaller images, use scikit-image (simpler, already loaded in memory)
            logger.info("Using scikit-image Sobel for moderate-sized image")

            # Normalize to 0-1 range if needed
            if image_array.dtype != np.float32 and image_array.dtype != np.float64:
                image_array = image_array.astype(np.float32)
                if image_array.max() > 1:
                    image_array = image_array / image_array.max()

            # Apply Sobel filter
            edges = filters.sobel(image_array)

            # Normalize to 0-255 uint8
            if edges.max() > 0:
                edges = (edges / edges.max() * 255).astype(np.uint8)
            else:
                edges = edges.astype(np.uint8)

            logger.info("Sobel filter complete (scikit-image mode)")
            return edges

    except Exception as e:
        logger.error(f"Error applying Sobel filter: {str(e)}")
        logger.error(traceback.format_exc())
        raise
