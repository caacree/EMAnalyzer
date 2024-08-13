# mims/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MIMSImageSetViewSet, MIMSImageViewSet

router = DefaultRouter()
router.register(r"mims_image_sets", MIMSImageSetViewSet)
router.register(r"mims_images", MIMSImageViewSet)

app_name = "mims"
urlpatterns = [
    path("", include(router.urls)),
]
