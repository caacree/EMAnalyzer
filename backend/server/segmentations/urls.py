from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SegmentationFileViewSet, CanvasSegmentedObjViewSet

app_name = 'segmentations'

router = DefaultRouter()
router.register(r'segmentation-files', SegmentationFileViewSet, basename='segmentationfile')
router.register(r'segmented-objects', CanvasSegmentedObjViewSet, basename='canvassegmentedobj')

urlpatterns = [
    path('', include(router.urls)),
]