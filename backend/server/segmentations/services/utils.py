"""Utility functions for segmentation management."""

import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def assign_parent_relationships(
    canvas_id: str, child_type: str, parent_type: str
) -> int:
    """
    Assign parent-child relationships between segmented objects.
    For example, assign mitochondria to their containing cells.

    Args:
        canvas_id: The canvas ID
        child_type: Name of child objects (e.g., "mitochondria")
        parent_type: Name of parent objects (e.g., "cell")

    Returns:
        Number of relationships created
    """
    from shapely.geometry import Point, Polygon

    from ..models import CanvasSegmentedObj

    try:
        # Get all parent and child objects for this canvas
        parents = CanvasSegmentedObj.objects.filter(
            canvas_id=canvas_id, name=parent_type
        )

        children = CanvasSegmentedObj.objects.filter(
            canvas_id=canvas_id,
            name=child_type,
            parent__isnull=True,  # Only unassigned children
        )

        relationships_created = 0

        # Create spatial index of parent polygons
        parent_polygons = {}
        for parent in parents:
            try:
                poly = Polygon(parent.polygon)
                if poly.is_valid:
                    parent_polygons[parent.id] = poly
            except:
                continue

        # Assign each child to containing parent
        for child in children:
            try:
                # Use centroid for containment check
                child_point = Point(child.centroid)

                # Find containing parent
                for parent_id, parent_poly in parent_polygons.items():
                    if parent_poly.contains(child_point):
                        child.parent_id = parent_id
                        child.save(update_fields=["parent"])
                        relationships_created += 1
                        break
            except:
                continue

        return relationships_created

    except Exception as e:
        logger.error(f"Error assigning parent relationships: {str(e)}")
        return 0


def delete_segmentation_file(segmentation_file_id: str) -> bool:
    """
    Delete a segmentation file and all its associated objects.

    Args:
        segmentation_file_id: The ID of the SegmentationFile to delete

    Returns:
        True if successful, False otherwise
    """
    from ..models import SegmentationFile

    try:
        with transaction.atomic():
            seg_file = SegmentationFile.objects.get(id=segmentation_file_id)

            # Delete will cascade to CanvasSegmentedObj due to foreign key
            seg_file.delete()

        return True

    except Exception as e:
        logger.error(f"Error deleting segmentation file: {str(e)}")
        return False
