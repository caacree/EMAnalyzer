from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404
import logging

from .models import SegmentationFile, CanvasSegmentedObj
from .serializers import (
    SegmentationFileSerializer,
    SegmentationFileUploadSerializer,
    CanvasSegmentedObjSerializer,
    CanvasSegmentedObjListSerializer,
    AssignParentRelationshipSerializer,
    SegmentationStatsSerializer,
)
from .services import (
    process_segmentation_file,
    assign_parent_relationships,
    delete_segmentation_file,
    convert_to_compressed_png,
)
from .tasks import process_segmentation_upload_async, process_segmentation_file_async

logger = logging.getLogger(__name__)


class SegmentationFileViewSet(viewsets.ModelViewSet):
    """ViewSet for SegmentationFile model."""

    queryset = SegmentationFile.objects.all()
    serializer_class = SegmentationFileSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        """Filter by canvas if specified."""
        queryset = super().get_queryset()
        canvas_id = self.request.query_params.get("canvas_id")

        if canvas_id:
            queryset = queryset.filter(canvas_id=canvas_id)

        return queryset

    def get_serializer_class(self):
        """Use different serializer for upload."""
        if self.action == "create":
            return SegmentationFileUploadSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        """Upload and process a segmentation file."""
        # Get the uploaded file
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {"error": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save the raw file directly (no conversion yet)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Save with PROCESSING status and raw file
        instance = serializer.save(
            status=SegmentationFile.Status.PROCESSING,
            raw_file=uploaded_file,
            progress=0,
            progress_message="Uploaded, preparing to process..."
        )

        # Trigger async task to generate DZI and compressed PNG
        task = process_segmentation_upload_async.delay(str(instance.id))

        # Store task ID for tracking
        instance.processing_info = {"task_id": task.id}
        instance.save(update_fields=["processing_info"])

        # Return the instance
        response_serializer = SegmentationFileSerializer(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Delete a segmentation file and all associated objects."""
        instance = self.get_object()
        success = delete_segmentation_file(instance.id)

        if success:
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(
                {"error": "Failed to delete segmentation file"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        """Reprocess a segmentation file."""
        instance = self.get_object()

        # Delete existing objects
        instance.segmented_objects.all().delete()

        # Reprocess
        task = process_segmentation_file_async.delay(str(instance.id))

        # Store task ID
        instance.processing_info = instance.processing_info or {}
        instance.processing_info["task_id"] = task.id
        instance.status = SegmentationFile.Status.PROCESSING
        instance.save(update_fields=["processing_info", "status"])

        if task:
            instance.refresh_from_db()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        else:
            return Response(
                {"error": "Failed to reprocess segmentation file"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        """Get the progress of a segmentation file processing."""
        instance = self.get_object()

        # Get Celery task status if available
        task_status = None
        if instance.processing_info and "task_id" in instance.processing_info:
            try:
                from celery.result import AsyncResult

                task_id = instance.processing_info["task_id"]
                task = AsyncResult(task_id)

                if task.state == "PENDING":
                    task_status = "waiting"
                elif task.state == "PROGRESS":
                    task_status = "processing"
                    if task.info:
                        instance.progress = task.info.get("current", instance.progress)
                        instance.progress_message = task.info.get(
                            "status", instance.progress_message
                        )
                elif task.state == "SUCCESS":
                    task_status = "completed"
                elif task.state == "FAILURE":
                    task_status = "failed"
            except:
                pass

        return Response(
            {
                "id": instance.id,
                "status": instance.status,
                "progress": instance.progress,
                "progress_message": instance.progress_message,
                "task_status": task_status,
                "object_count": (
                    instance.segmented_objects.count()
                    if instance.status == "completed"
                    else 0
                ),
            }
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get segmentation statistics for a canvas."""
        canvas_id = request.query_params.get("canvas_id")

        if not canvas_id:
            return Response(
                {"error": "canvas_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get statistics
        files = SegmentationFile.objects.filter(canvas_id=canvas_id)
        objects = CanvasSegmentedObj.objects.filter(canvas_id=canvas_id)

        # Group by object type
        object_types = (
            objects.values("name")
            .annotate(count=Count("id"), total_area=Sum("area"))
            .order_by("-count")
        )

        stats_data = {
            "canvas_id": canvas_id,
            "total_objects": objects.count(),
            "object_types": list(object_types),
            "total_area_covered": objects.aggregate(Sum("area"))["area__sum"] or 0,
            "files_count": files.count(),
        }

        serializer = SegmentationStatsSerializer(data=stats_data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class CanvasSegmentedObjViewSet(viewsets.ModelViewSet):
    """ViewSet for CanvasSegmentedObj model."""

    queryset = CanvasSegmentedObj.objects.all()
    serializer_class = CanvasSegmentedObjSerializer

    def get_queryset(self):
        """Filter by various parameters."""
        queryset = super().get_queryset()

        # Filter by canvas
        canvas_id = self.request.query_params.get("canvas_id")
        if canvas_id:
            queryset = queryset.filter(canvas_id=canvas_id)

        # Filter by source file
        source_file_id = self.request.query_params.get("source_file_id")
        if source_file_id:
            queryset = queryset.filter(source_file_id=source_file_id)

        # Filter by object type
        object_type = self.request.query_params.get("type")
        if object_type:
            queryset = queryset.filter(name=object_type)

        # Filter by parent
        parent_id = self.request.query_params.get("parent_id")
        if parent_id:
            if parent_id == "null":
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)

        # Include only objects with minimum area
        min_area = self.request.query_params.get("min_area")
        if min_area:
            queryset = queryset.filter(area__gte=float(min_area))

        return queryset

    def get_serializer_class(self):
        """Use lightweight serializer for list action."""
        if self.action == "list":
            # Check if detailed view is requested
            if self.request.query_params.get("detailed") == "true":
                return CanvasSegmentedObjSerializer
            return CanvasSegmentedObjListSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["post"])
    def assign_parents(self, request):
        """Assign parent-child relationships between objects."""
        serializer = AssignParentRelationshipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        relationships_created = assign_parent_relationships(
            canvas_id=serializer.validated_data["canvas_id"],
            child_type=serializer.validated_data["child_type"],
            parent_type=serializer.validated_data["parent_type"],
        )

        return Response(
            {
                "relationships_created": relationships_created,
                "message": f"Successfully assigned {relationships_created} parent relationships",
            }
        )

    @action(detail=False, methods=["get"])
    def types(self, request):
        """Get all unique object types for a canvas."""
        canvas_id = request.query_params.get("canvas_id")

        if not canvas_id:
            return Response(
                {"error": "canvas_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        types = (
            CanvasSegmentedObj.objects.filter(canvas_id=canvas_id)
            .values_list("name", flat=True)
            .distinct()
        )

        return Response(list(types))

    @action(detail=False, methods=["delete"])
    def bulk_delete(self, request):
        """Bulk delete objects by type or source file."""
        canvas_id = request.query_params.get("canvas_id")
        object_type = request.query_params.get("type")
        source_file_id = request.query_params.get("source_file_id")

        if not canvas_id:
            return Response(
                {"error": "canvas_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        queryset = CanvasSegmentedObj.objects.filter(canvas_id=canvas_id)

        if object_type:
            queryset = queryset.filter(name=object_type)

        if source_file_id:
            queryset = queryset.filter(source_file_id=source_file_id)

        count = queryset.count()
        queryset.delete()

        return Response(
            {"deleted": count, "message": f"Successfully deleted {count} objects"}
        )

    @action(detail=True, methods=["get"])
    def children(self, request, pk=None):
        """Get all children of a segmented object."""
        parent = self.get_object()
        children = parent.children.all()

        # Use lightweight serializer
        serializer = CanvasSegmentedObjListSerializer(children, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def hierarchy(self, request):
        """Get hierarchical structure of objects for a canvas."""
        canvas_id = request.query_params.get("canvas_id")

        if not canvas_id:
            return Response(
                {"error": "canvas_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get top-level objects (no parent)
        top_level = CanvasSegmentedObj.objects.filter(
            canvas_id=canvas_id, parent__isnull=True
        ).prefetch_related("children")

        def build_hierarchy(obj):
            """Recursively build hierarchy."""
            children = obj.children.all()
            return {
                "id": str(obj.id),
                "name": obj.name,
                "area": obj.area,
                "children": [build_hierarchy(child) for child in children],
            }

        hierarchy = [build_hierarchy(obj) for obj in top_level]

        return Response(hierarchy)
