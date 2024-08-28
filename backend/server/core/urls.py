# urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CanvasViewSet

router = DefaultRouter()
router.register(r"canvas", CanvasViewSet)

app_name = "core"
urlpatterns = [
    path("", include(router.urls)),
]
