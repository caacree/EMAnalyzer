from rest_framework import viewsets
from .models import EMImage
from .serializers import EMImageSerializer


class EMImageViewSet(viewsets.ModelViewSet):
    queryset = EMImage.objects.all()
    serializer_class = EMImageSerializer
