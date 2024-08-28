from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from .models import Canvas
from .serializers import CanvasListSerializer, CanvasDetailSerializer


class CanvasViewSet(viewsets.ModelViewSet):
    queryset = Canvas.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return CanvasListSerializer
        if self.action == "retrieve":
            return CanvasDetailSerializer
        return CanvasListSerializer
