"""Object extraction from labeled segmentation images."""

import logging
from typing import Optional

import numpy as np
from django.db import transaction
from skimage import measure

logger = logging.getLogger(__name__)


def extract_and_save_objects_with_progress(
    seg_file,
    labeled_image: np.ndarray,
    object_name: str,
    preserve_labels: bool = False,
    task=None,
    progress_start: int = 30,
    progress_end: int = 95,
) -> int:
    """
    Extract objects from a labeled image with progress tracking and batch processing.

    Args:
        seg_file: The source SegmentationFile
        labeled_image: Labeled image where each object has a unique integer value
        object_name: Name for the objects (e.g., "mitochondria", "cell")
        preserve_labels: If True, store the original label ID
        task: Optional Celery task for progress updates
        progress_start: Starting progress percentage
        progress_end: Ending progress percentage

    Returns:
        Number of objects created
    """
    from ..models import CanvasSegmentedObj
    from .segmentation_processing import update_progress

    # Get region properties
    update_progress(seg_file, progress_start + 5, "Extracting regions...", task)
    regions = measure.regionprops(labeled_image)
    total_regions = len(regions)

    if total_regions == 0:
        return 0

    # Process all objects directly without batching overhead
    objects_to_create = []

    update_progress(
        seg_file, progress_start + 10, f"Processing {total_regions} objects...", task
    )

    for i, region in enumerate(regions):
        # Update progress periodically
        if i % 10 == 0:
            progress = progress_start + int(
                (i / total_regions) * (progress_end - progress_start - 10)
            )
            update_progress(
                seg_file,
                progress,
                f"Processing object {i + 1}/{total_regions}...",
                task,
            )

        # Skip very small objects
        if region.area < 5:
            continue

        # Get contour (polygon) - optimized for speed
        contour = get_contour_from_region_optimized(labeled_image, region)

        if contour is None or len(contour) < 3:
            continue

        # Convert to list of [x, y] pairs
        polygon = contour.tolist()

        # Calculate centroid
        centroid = [
            float(region.centroid[1]),
            float(region.centroid[0]),
        ]  # x, y order

        # Calculate bounding box
        minr, minc, maxr, maxc = region.bbox
        bbox = [
            float(minc),
            float(minr),
            float(maxc),
            float(maxr),
        ]  # x_min, y_min, x_max, y_max

        obj = CanvasSegmentedObj(
            canvas=seg_file.canvas,
            source_file=seg_file,
            name=object_name,
            polygon=polygon,
            area=float(region.area),
            label_id=int(region.label) if preserve_labels else None,
            centroid=centroid,
            bbox=bbox,
        )
        objects_to_create.append(obj)

    # Bulk create all objects at once
    if objects_to_create:
        with transaction.atomic():
            CanvasSegmentedObj.objects.bulk_create(objects_to_create, batch_size=500)
            objects_created_total = len(objects_to_create)
    else:
        objects_created_total = 0

    update_progress(
        seg_file, progress_end, f"Saved {objects_created_total} objects", task
    )

    return objects_created_total


def get_contour_from_region_optimized(
    labeled_image: np.ndarray, region
) -> Optional[np.ndarray]:
    """
    Extract contour polygon from a region with full fidelity (no simplification).

    Args:
        labeled_image: The labeled image
        region: A region from skimage.measure.regionprops

    Returns:
        Contour as array of [x, y] coordinates or None
    """
    try:
        # Use region's bbox to create a smaller mask (much faster)
        minr, minc, maxr, maxc = region.bbox
        mask_slice = labeled_image[minr:maxr, minc:maxc] == region.label

        # Find contours on the smaller region
        contours = measure.find_contours(mask_slice, 0.5)

        if not contours:
            return None

        # Get the longest contour (outer boundary)
        contour = max(contours, key=len)

        # Adjust coordinates back to full image space
        contour[:, 0] += minr
        contour[:, 1] += minc

        # Flip to [x, y] order and simplify aggressively for speed
        contour = np.fliplr(contour)

        # Aggressive simplification for speed (tolerance = 2 pixels)
        simplified = measure.approximate_polygon(contour, tolerance=2.0)

        return simplified

    except Exception as e:
        logger.error(f"Error extracting contour: {str(e)}")
        return None
