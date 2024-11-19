from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
import json
from rest_framework.decorators import action
from mims.services.registration_utils import (
    mask_to_polygon,
)
from core.models import Canvas
from .models import MIMSAlignment, MIMSImageSet, MIMSImage
from .serializers import MIMSImageSetSerializer, MIMSImageSerializer
from .tasks import (
    create_registration_images_task,
    preprocess_mims_image_set,
    register_images_task,
)
from mims.services.orient_images import orient_viewset
import os
from PIL import Image
import numpy as np

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
import torch
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
from pathlib import Path
import cv2


predictors = {}


class MIMSImageSetViewSet(viewsets.ModelViewSet):
    queryset = MIMSImageSet.objects.all()
    serializer_class = MIMSImageSetSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        canvas_id = data.get("canvas")
        canvas = Canvas.objects.get(id=canvas_id)
        has_files = any([file.startswith("file_") for file in data.keys()])
        if not has_files:
            return Response(
                {"message": "No files were uploaded"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        image_set = MIMSImageSet.objects.create(canvas=canvas)

        for file_key in data.keys():
            if file_key.startswith("file_"):
                file = data[file_key]
                MIMSImage.objects.create(
                    canvas=canvas,
                    image_set=image_set,
                    file=file,
                )
        preprocess_mims_image_set.delay(image_set.id)

        serializer = MIMSImageSetSerializer(image_set)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit_viewset_alignment_points(self, request, pk=None):
        data = request.data
        mims_image_set = self.get_object()
        viewset_points = data.get("points")
        isotope = data.get("isotope", "SE")
        orient_viewset(mims_image_set, viewset_points, isotope)
        return Response(status=status.HTTP_200_OK)


class MIMSImageViewSet(viewsets.ModelViewSet):
    queryset = MIMSImage.objects.all()
    serializer_class = MIMSImageSerializer

    @action(detail=True, methods=["post"])
    def set_alignment(self, request, pk=None):
        # Get the MIMSImage instance
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        """if mims_image.status == "REGISTERING":
            return Response(
                {"message": "MIMS image is already undergoing registration"},
                status=status.HTTP_400_BAD_REQUEST,
            )"""
        mims_image.status = "REGISTERING"
        mims_image.save()

        # Extract data from the request
        data = request.data
        rotation = data.get("rotation", 0)
        flip = data.get("flip", False)
        x_offset = data.get("xOffset", 0)
        y_offset = data.get("yOffset", 0)

        # Remove existing alignments for this image
        mims_image.alignments.all().delete()

        # Create a new alignment with status 'USER_ROUGH_ALIGNMENT'
        MIMSAlignment.objects.create(
            mims_image=mims_image,
            x_offset=x_offset,
            y_offset=y_offset,
            rotation_degrees=rotation,
            flip_hor=flip,
            scale=mims_image.pixel_size_nm / mims_image.image_set.canvas.pixel_size_nm,
            status="USER_ROUGH_ALIGNMENT",
        )

        create_registration_images_task.delay(mims_image.id)
        mims_image.status = "AWAITING_REGISTRATION"
        mims_image.save()

        return Response(
            {"message": "Alignment updated successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def get_segment_prediction(self, request, pk=None):
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        image_key = request.data.get("image_key", "em")
        predictor_key = f"{pk}_{image_key}"
        if predictor_key not in predictors:
            mims_path = Path(mims_image.file.path)
            reg_loc = os.path.join(mims_path.parent, mims_path.stem, "registration")
            if image_key != "em":
                reg_loc = os.path.join(mims_path.parent, mims_path.stem, "isotopes")
                image_key = f"{image_key}_autocontrast"
            image = np.array(Image.open(os.path.join(reg_loc, f"{image_key}.png")))

            # Convert image to 3 channels if it's single-channel
            if image.ndim == 2:  # If the image is grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            device = torch.device("mps")

            checkpoint = "/Users/chris/Documents/lab/emAnalysis/backend/segment-anything-2/checkpoints/sam2_hiera_large.pt"
            model_cfg = "sam2_hiera_l.yaml"
            predictor = SAM2ImagePredictor(build_sam2(model_cfg, checkpoint, device))

            predictor.set_image(image)
            predictors[predictor_key] = predictor

        predictor = predictors[predictor_key]
        input_points = np.array(request.data.get("point_coords"))
        input_labels = np.array(request.data.get("point_labels"))
        # print the max and min for each of x and y in the input points
        masks, scores, logits = predictor.predict(
            point_coords=input_points, point_labels=input_labels
        )
        highest_mask = masks[np.argmax(scores)]
        polygons = mask_to_polygon(highest_mask)
        # print max and min x and y of the polygon
        return Response({"polygons": polygons})

    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        """if mims_image.status == "REGISTERING":
            return Response(
                {"message": "MIMS image is not ready for registration"},
                status=status.HTTP_400_BAD_REQUEST,
            )"""
        # mims_image.status = "REGISTERING"
        # mims_image.save()

        em_shapes = request.data.get("em_shapes")
        mims_shapes = request.data.get("mims_shapes")

        mims_path = Path(mims_image.file.path)
        reg_loc = os.path.join(mims_path.parent, mims_path.stem, "registration")
        with open(os.path.join(reg_loc, "reg_shapes.json"), "w") as shapes_file:
            shapes_file.write(
                json.dumps({"em_shapes": em_shapes, "mims_shapes": mims_shapes})
            )

        register_images_task.delay(mims_image.id)
        global predictors
        predictors = {}
        return Response(
            {
                "message": "Registration processing",
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        mims_image.status = "PREPROCESSING"
        mims_image.alignments.all().delete()
        mims_image.save()
        return Response(
            {"message": "MIMS image reset successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def outside_canvas(self, request, pk=None):
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        mims_image.status = "OUTSIDE_CANVAS"
        # mims_image.alignments.all().delete()
        mims_image.save()
        return Response(
            {"message": "MIMS image is outside the canvas"}, status=status.HTTP_200_OK
        )
