"""Main segmentation processing logic."""

import logging
import traceback

import numpy as np
from skimage import measure, morphology

logger = logging.getLogger(__name__)


def process_segmentation_file(segmentation_file_id: str) -> bool:
    """
    Main entry point for processing a segmentation file.
    Dispatches to appropriate processor based on upload type.

    Returns True if successful, False otherwise.
    """
    from ..models import SegmentationFile
    from .image_filters import load_tiff_file

    try:
        seg_file = SegmentationFile.objects.get(id=segmentation_file_id)
        seg_file.status = SegmentationFile.Status.PROCESSING
        seg_file.save(update_fields=["status"])

        # Load the image from the file field
        image = load_tiff_file(seg_file.file.path)

        if seg_file.upload_type == SegmentationFile.UploadType.PROBABILITY:
            success = _process_probability_map(seg_file, image)
        else:  # LABEL
            success = _process_label_map(seg_file, image)

        if success:
            seg_file.status = SegmentationFile.Status.COMPLETED
        else:
            seg_file.status = SegmentationFile.Status.FAILED

        seg_file.save(update_fields=["status"])
        return success

    except Exception as e:
        logger.error(
            f"Error processing segmentation file {segmentation_file_id}: {str(e)}"
        )
        logger.error(traceback.format_exc())

        try:
            seg_file.status = SegmentationFile.Status.FAILED
            seg_file.processing_info = {"error": str(e)}
            seg_file.save(update_fields=["status", "processing_info"])
        except:
            pass

        return False


def process_segmentation_file_with_progress(
    segmentation_file_id: str, task=None
) -> bool:
    """
    Main entry point for processing with progress tracking.
    Used by async tasks.

    Args:
        segmentation_file_id: ID of the segmentation file
        task: Celery task instance for progress updates

    Returns:
        True if successful, False otherwise.
    """
    from ..models import SegmentationFile
    from .image_filters import load_tiff_file

    try:
        seg_file = SegmentationFile.objects.get(id=segmentation_file_id)
        seg_file.status = SegmentationFile.Status.PROCESSING
        seg_file.progress = 0
        seg_file.progress_message = "Starting processing..."
        seg_file.save(update_fields=["status", "progress", "progress_message"])

        # Load the image from the file field
        update_progress(seg_file, 5, "Loading image file...", task)
        image = load_tiff_file(seg_file.file.path)

        update_progress(seg_file, 10, "Image loaded, analyzing...", task)

        if seg_file.upload_type == SegmentationFile.UploadType.PROBABILITY:
            success = process_probability_map_with_progress(seg_file, image, task)
        else:  # LABEL
            success = process_label_map_with_progress(seg_file, image, task)

        if success:
            seg_file.status = SegmentationFile.Status.COMPLETED
            seg_file.progress = 100
            seg_file.progress_message = "Processing complete"
        else:
            seg_file.status = SegmentationFile.Status.FAILED

        seg_file.save(update_fields=["status", "progress", "progress_message"])
        return success

    except Exception as e:
        logger.error(
            f"Error processing segmentation file {segmentation_file_id}: {str(e)}"
        )
        logger.error(traceback.format_exc())

        try:
            seg_file.status = SegmentationFile.Status.FAILED
            seg_file.progress_message = f"Error: {str(e)}"
            seg_file.processing_info = {"error": str(e)}
            seg_file.save(
                update_fields=["status", "progress_message", "processing_info"]
            )
        except:
            pass

        return False


def update_progress(seg_file, progress: int, message: str, task=None):
    """
    Update progress for a segmentation file.

    Args:
        seg_file: SegmentationFile instance
        progress: Progress percentage (0-100)
        message: Progress message
        task: Optional Celery task for meta updates
    """
    seg_file.progress = progress
    seg_file.progress_message = message
    seg_file.save(update_fields=["progress", "progress_message"])

    if task:
        task.update_state(
            state="PROGRESS",
            meta={"current": progress, "total": 100, "status": message},
        )


def process_probability_map_with_progress(seg_file, image: np.ndarray, task=None) -> bool:
    """
    Process a probability map with progress tracking.

    Args:
        seg_file: The SegmentationFile instance
        image: The probability map as a numpy array (stored as uint8, 0-255 range)
        task: Optional Celery task for progress updates

    Returns:
        True if successful, False otherwise
    """
    from .object_extraction import extract_and_save_objects_with_progress

    try:
        threshold = seg_file.threshold or 0.5
        min_area = seg_file.min_area or 10

        update_progress(seg_file, 15, f"Applying threshold {threshold}...", task)

        # Convert from uint8 (0-255) back to 0-1 range for processing
        if image.dtype == np.uint8:
            image = image.astype(np.float32) / 255.0
        elif image.max() > 1:
            # Handle other cases where normalization is needed
            image = image / image.max()

        # Threshold the image
        binary = image > threshold

        update_progress(seg_file, 20, "Filling holes in objects...", task)

        # Fill holes in objects
        binary = morphology.remove_small_holes(binary)

        # Remove small objects
        binary = morphology.remove_small_objects(binary, min_size=int(min_area))

        update_progress(seg_file, 30, "Labeling connected components...", task)

        # Label connected components
        labeled = measure.label(binary, connectivity=1)

        # Extract objects with progress
        objects_created = extract_and_save_objects_with_progress(
            seg_file=seg_file,
            labeled_image=labeled,
            object_name=seg_file.name,
            task=task,
            progress_start=30,
            progress_end=95,
        )

        update_progress(seg_file, 98, f"Created {objects_created} objects", task)

        seg_file.processing_info = {
            "objects_created": objects_created,
            "threshold_used": threshold,
            "min_area_used": min_area,
        }
        seg_file.save(update_fields=["processing_info"])

        return True

    except Exception as e:
        logger.error(f"Error processing probability map: {str(e)}")
        seg_file.processing_info = {"error": str(e)}
        seg_file.save(update_fields=["processing_info"])
        return False


def _process_probability_map(seg_file, image: np.ndarray) -> bool:
    """
    Process a probability map by thresholding and extracting objects (no progress tracking).

    Args:
        seg_file: The SegmentationFile instance
        image: The probability map as a numpy array (stored as uint8, 0-255 range)

    Returns:
        True if successful, False otherwise
    """
    from .object_extraction import extract_and_save_objects_with_progress

    try:
        threshold = seg_file.threshold or 0.5
        min_area = seg_file.min_area or 10

        # Convert from uint8 (0-255) back to 0-1 range for processing
        if image.dtype == np.uint8:
            image = image.astype(np.float32) / 255.0
        elif image.max() > 1:
            # Handle other cases where normalization is needed
            image = image / image.max()

        # Threshold the image
        binary = image > threshold

        # Fill holes in objects
        binary = morphology.remove_small_holes(binary)

        # Remove small objects
        binary = morphology.remove_small_objects(binary, min_size=int(min_area))

        # Label connected components
        labeled = measure.label(binary, connectivity=2)

        # Extract objects (without progress tracking)
        objects_created = extract_and_save_objects_with_progress(
            seg_file=seg_file, labeled_image=labeled, object_name=seg_file.name
        )

        seg_file.processing_info = {
            "objects_created": objects_created,
            "threshold_used": threshold,
            "min_area_used": min_area,
        }
        seg_file.save(update_fields=["processing_info"])

        return True

    except Exception as e:
        logger.error(f"Error processing probability map: {str(e)}")
        seg_file.processing_info = {"error": str(e)}
        seg_file.save(update_fields=["processing_info"])
        return False


def process_label_map_with_progress(seg_file, image: np.ndarray, task=None) -> bool:
    """
    Process a label map with progress tracking.

    Args:
        seg_file: The SegmentationFile instance
        image: The label map as a numpy array
        task: Optional Celery task for progress updates

    Returns:
        True if successful, False otherwise
    """
    from .object_extraction import extract_and_save_objects_with_progress

    try:
        update_progress(seg_file, 15, "Analyzing label map...", task)

        # Ensure integer labels
        if image.dtype == np.float32 or image.dtype == np.float64:
            image = image.astype(np.int16)

        # Get unique labels (excluding 0 which is background)
        unique_labels = np.unique(image)
        unique_labels = unique_labels[unique_labels != 0]

        update_progress(seg_file, 20, f"Found {len(unique_labels)} unique labels", task)

        # Create a labeled image (already is one, but ensure proper format)
        labeled = (
            image.astype(np.int16) if image.max() < 65536 else image.astype(np.int32)
        )

        # Extract objects with progress tracking
        objects_created = extract_and_save_objects_with_progress(
            seg_file=seg_file,
            labeled_image=labeled,
            object_name=seg_file.name,
            preserve_labels=True,
            task=task,
            progress_start=20,
            progress_end=95,
        )

        update_progress(seg_file, 98, f"Created {objects_created} objects", task)

        seg_file.processing_info = {
            "objects_created": objects_created,
            "unique_labels": len(unique_labels),
        }
        seg_file.save(update_fields=["processing_info"])

        return True

    except Exception as e:
        logger.error(f"Error processing label map: {str(e)}")
        seg_file.processing_info = {"error": str(e)}
        seg_file.save(update_fields=["processing_info"])
        return False


def _process_label_map(seg_file, image: np.ndarray) -> bool:
    """
    Process a label map where each unique value represents a different object (no progress tracking).

    Args:
        seg_file: The SegmentationFile instance
        image: The label map as a numpy array

    Returns:
        True if successful, False otherwise
    """
    from .object_extraction import extract_and_save_objects_with_progress

    try:
        # Ensure integer labels
        if image.dtype == np.float32 or image.dtype == np.float64:
            image = image.astype(np.int32)

        # Get unique labels (excluding 0 which is background)
        unique_labels = np.unique(image)
        unique_labels = unique_labels[unique_labels != 0]

        # Create a labeled image (already is one, but ensure proper format)
        labeled = image.astype(np.int32)

        # Extract objects (without progress tracking)
        objects_created = extract_and_save_objects_with_progress(
            seg_file=seg_file,
            labeled_image=labeled,
            object_name=seg_file.name,
            preserve_labels=True,
        )

        seg_file.processing_info = {
            "objects_created": objects_created,
            "unique_labels": len(unique_labels),
        }
        seg_file.save(update_fields=["processing_info"])

        return True

    except Exception as e:
        logger.error(f"Error processing label map: {str(e)}")
        seg_file.processing_info = {"error": str(e)}
        seg_file.save(update_fields=["processing_info"])
        return False
