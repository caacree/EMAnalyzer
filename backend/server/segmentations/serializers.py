from rest_framework import serializers
from .models import SegmentationFile, CanvasSegmentedObj


class SegmentationFileSerializer(serializers.ModelSerializer):
    """Serializer for SegmentationFile model."""

    object_count = serializers.SerializerMethodField()
    canvas_name = serializers.CharField(source='canvas.name', read_only=True)
    file_url = serializers.SerializerMethodField()
    dzi_url = serializers.SerializerMethodField()
    sobel_dzi_url = serializers.SerializerMethodField()
    sam2_dzi_url = serializers.SerializerMethodField()

    class Meta:
        model = SegmentationFile
        fields = [
            'id',
            'canvas',
            'canvas_name',
            'name',
            'raw_file',
            'file',
            'file_url',
            'dzi_file',
            'dzi_url',
            'sobel_dzi_file',
            'sobel_dzi_url',
            'sam2_dzi_file',
            'sam2_dzi_url',
            'upload_type',
            'threshold',
            'min_area',
            'status',
            'progress',
            'progress_message',
            'processing_info',
            'object_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'raw_file', 'file', 'file_url', 'dzi_file', 'dzi_url', 'sobel_dzi_file', 'sobel_dzi_url', 'sam2_dzi_file', 'sam2_dzi_url', 'status', 'progress', 'progress_message', 'processing_info', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        """Get the file URL if it exists."""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_dzi_url(self, obj):
        """Get the DZI file URL if it exists."""
        if obj.dzi_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.dzi_file.url)
            return obj.dzi_file.url
        return None

    def get_sobel_dzi_url(self, obj):
        """Get the Sobel DZI file URL if it exists."""
        if obj.sobel_dzi_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.sobel_dzi_file.url)
            return obj.sobel_dzi_file.url
        return None

    def get_sam2_dzi_url(self, obj):
        """Get the SAM2 DZI file URL if it exists."""
        if obj.sam2_dzi_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.sam2_dzi_file.url)
            return obj.sam2_dzi_file.url
        return None
    
    def get_object_count(self, obj):
        """Get the count of segmented objects from this file."""
        return obj.segmented_objects.count()
    
    def validate(self, data):
        """Validate the segmentation file data."""
        upload_type = data.get('upload_type', SegmentationFile.UploadType.PROBABILITY)
        
        # For probability maps, require threshold and min_area
        if upload_type == SegmentationFile.UploadType.PROBABILITY:
            if data.get('threshold') is None:
                raise serializers.ValidationError({
                    'threshold': 'Threshold is required for probability maps'
                })
            if not 0 <= data['threshold'] <= 1:
                raise serializers.ValidationError({
                    'threshold': 'Threshold must be between 0 and 1'
                })
            if data.get('min_area') is None:
                data['min_area'] = 10  # Default value
        
        return data


class SegmentationFileUploadSerializer(serializers.ModelSerializer):
    """Serializer specifically for creating segmentation records with file upload."""

    class Meta:
        model = SegmentationFile
        fields = [
            'id',
            'canvas',
            'name',
            'upload_type',
            'threshold',
            'min_area'
        ]


class CanvasSegmentedObjSerializer(serializers.ModelSerializer):
    """Serializer for CanvasSegmentedObj model."""
    
    canvas_name = serializers.CharField(source='canvas.name', read_only=True)
    source_file_name = serializers.CharField(source='source_file.name', read_only=True)
    parent_id = serializers.UUIDField(source='parent.id', read_only=True, allow_null=True)
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CanvasSegmentedObj
        fields = [
            'id',
            'canvas',
            'canvas_name',
            'source_file',
            'source_file_name',
            'name',
            'polygon',
            'area',
            'parent',
            'parent_id',
            'children_count',
            'label_id',
            'centroid',
            'bbox',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_children_count(self, obj):
        """Get the count of child objects."""
        return obj.children.count()


class CanvasSegmentedObjListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing segmented objects."""
    
    parent_id = serializers.UUIDField(source='parent.id', read_only=True, allow_null=True)
    
    class Meta:
        model = CanvasSegmentedObj
        fields = [
            'id',
            'name',
            'area',
            'parent_id',
            'label_id',
            'centroid',
            'bbox'
        ]


class AssignParentRelationshipSerializer(serializers.Serializer):
    """Serializer for assigning parent-child relationships."""
    
    canvas_id = serializers.UUIDField()
    child_type = serializers.CharField(max_length=100)
    parent_type = serializers.CharField(max_length=100)
    
    def validate(self, data):
        """Validate that both object types exist for the canvas."""
        from .models import CanvasSegmentedObj
        
        canvas_id = data['canvas_id']
        
        # Check if child objects exist
        if not CanvasSegmentedObj.objects.filter(
            canvas_id=canvas_id,
            name=data['child_type']
        ).exists():
            raise serializers.ValidationError({
                'child_type': f"No objects of type '{data['child_type']}' found for this canvas"
            })
        
        # Check if parent objects exist
        if not CanvasSegmentedObj.objects.filter(
            canvas_id=canvas_id,
            name=data['parent_type']
        ).exists():
            raise serializers.ValidationError({
                'parent_type': f"No objects of type '{data['parent_type']}' found for this canvas"
            })
        
        return data


class SegmentationStatsSerializer(serializers.Serializer):
    """Serializer for segmentation statistics."""
    
    canvas_id = serializers.UUIDField()
    total_objects = serializers.IntegerField()
    object_types = serializers.ListField(child=serializers.DictField())
    total_area_covered = serializers.FloatField()
    files_count = serializers.IntegerField()