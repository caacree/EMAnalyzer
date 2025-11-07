"""PNG conversion utilities for large segmentation files."""

import io
import logging
import os
import traceback

import pyvips
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


def convert_to_compressed_png(uploaded_file, upload_type: str) -> ContentFile:
    """
    Convert an uploaded segmentation file to a compressed PNG using pyvips for efficiency.

    Uses streaming processing to handle very large files (20k-50k+ pixels, multi-GB TIFFs)
    without loading entire image into memory.

    For probability maps: Convert to uint8 (0-255 range)
    For label maps: Convert to uint8 or uint16 based on number of unique values

    Args:
        uploaded_file: Django UploadedFile or file-like object
        upload_type: 'probability' or 'label'

    Returns:
        ContentFile containing the compressed PNG data
    """
    from ..models import SegmentationFile

    try:
        # Get file path - handle both Django UploadedFile and file wrappers
        if hasattr(uploaded_file, "file_path"):
            # Custom file wrapper from tasks.py
            file_path = uploaded_file.file_path
        elif hasattr(uploaded_file, "temporary_file_path"):
            # Django UploadedFile with temp file
            file_path = uploaded_file.temporary_file_path()
        elif hasattr(uploaded_file, "path"):
            # Django FileField
            file_path = uploaded_file.path
        else:
            # In-memory file - save to temp location
            import tempfile

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(uploaded_file.name)[1]
            ) as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                file_path = tmp.name

        logger.info(f"Converting {file_path} to PNG using pyvips")

        # Load with pyvips - use random access for conversions that need multiple passes
        # Sequential access fails when we need to compute max() then process again
        img = pyvips.Image.new_from_file(file_path, access="random")

        logger.info(
            f"Image dimensions: {img.width}x{img.height}, bands: {img.bands}, format: {img.format}"
        )

        # Convert to single band if multi-band
        if img.bands > 1:
            logger.info(f"Extracting first band from {img.bands}-band image")
            img = img[0]

        # Convert based on upload type
        if upload_type == SegmentationFile.UploadType.PROBABILITY:
            # For probability maps, normalize and convert to uint8
            logger.info("Converting probability map to uint8")

            # Get max value for normalization
            max_val = img.max()
            logger.info(f"Max value in image: {max_val}")

            # Normalize to 0-255 uint8 range
            if max_val > 255:
                # Normalize and scale to uint8
                img = img / max_val * 255

            # Cast to uint8
            img = img.cast("uchar")

        else:
            # For label maps, convert to smallest compatible format
            logger.info("Converting label map to optimal format")

            # Get max value to determine best format
            max_val = img.max()
            logger.info(f"Max label value: {max_val}")

            if max_val <= 255:
                logger.info("Converting to uint8")
                img = img.cast("uchar")
            elif max_val <= 65535:
                logger.info("Converting to uint16")
                img = img.cast("ushort")
            else:
                logger.warning(
                    f"Label map has {max_val} labels, exceeds uint16 range. Converting to uint16 with modulo."
                )
                # Too many labels for uint16, take modulo (or could error)
                img = img % 65536
                img = img.cast("ushort")

        # Write to PNG buffer using pyvips (streaming, efficient compression)
        # compression=6 is a good balance: still reduces size significantly but uses much less
        # memory/CPU than level 9 (which caused OOM crashes on large files)
        logger.info("Compressing to PNG with level 6 (balance of size/speed/memory)")
        png_data = img.pngsave_buffer(compression=6)

        logger.info(f"Compressed PNG size: {len(png_data) / 1024 / 1024:.2f} MB")

        # Create ContentFile
        png_filename = os.path.splitext(uploaded_file.name)[0] + ".png"
        return ContentFile(png_data, name=png_filename)

    except Exception as e:
        logger.error(f"Error converting file to PNG: {str(e)}")
        logger.error(traceback.format_exc())
        raise
