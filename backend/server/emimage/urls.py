# urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EMImageViewSet

router = DefaultRouter()
router.register(r"em_images", EMImageViewSet)

app_name = "emimage"
urlpatterns = [
    path("", include(router.urls)),
]
