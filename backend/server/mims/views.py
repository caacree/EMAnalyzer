from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.response import Response
import json
from rest_framework.decorators import action
from mims.services.image_utils import image_from_im_file
from mims.services.registration_utils import (
    mask_to_polygon,
)
from mims.services.prepare_registration_images import prepare_registration_images
from core.models import Canvas
from .models import MIMSAlignment, MIMSImageSet, MIMSImage
from .serializers import MIMSImageSetSerializer, MIMSImageSerializer
from .tasks import (
    create_registration_images_task,
    preprocess_mims_image_set,
    register_images_task,
    orient_viewset_task,
)
from mims.services.register import register_images
from mims.services.orient_images import orient_viewset
import os
from PIL import Image
import numpy as np

import torch
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
from pathlib import Path
import cv2

checkpoint = "/Users/chris/Documents/lab/emAnalysis/backend/segment-anything-2/checkpoints/sam2.1_hiera_large.pt"
model_cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"
sam2_model = build_sam2(model_cfg, checkpoint, device="mps")
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

    @action(detail=True, methods=["get"])
    def is_segmentation_ready(self, request, pk=None):
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        isotopes = [i.name for i in mims_image.isotopes.all()]
        for image_key in isotopes + ["em"]:
            if image_key not in predictors:
                return Response(False)
        return Response(True)

    @action(detail=True, methods=["get"])
    def prepare_for_segmentation(self, request, pk=None):
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        prepare_registration_images(mims_image)
        mims_bbox = mims_image.canvas_bbox
        # calculate em bbox by finding the min and max x and y of the canvas bbox
        em_bbox = [
            max(0, int(min([m[0] for m in mims_bbox])) - 1000),
            max(0, int(min([m[1] for m in mims_bbox])) - 1000),
            int(max([m[0] for m in mims_bbox])) + 1000,
            int(max([m[1] for m in mims_bbox])) + 1000,
        ]

        isotopes = [i.name for i in mims_image.isotopes.all()]

        # Prepare predictors for each possible image_key and 'em'
        image_keys = isotopes + ["em"]
        em = np.array(Image.open(mims_image.canvas.images.first().file.path))
        predictor = SAM2ImagePredictor(sam2_model)

        for image_key in image_keys:
            predictor_key = f"{pk}_{image_key}"
            if predictor_key not in predictors:
                if image_key != "em":
                    image = image_from_im_file(mims_image.file.path, image_key, True)
                else:
                    em_cropped = em[em_bbox[1] : em_bbox[3], em_bbox[0] : em_bbox[2]]
                    image = em_cropped
                # Convert image to 3 channels if it's single-channel
                if image.ndim == 2:  # If the image is grayscale
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

                print(f"Setting image for {predictor_key}")
                predictor.set_image(image)
                predictors[predictor_key] = predictor
        full_em_predictor = SAM2ImagePredictor(sam2_model)
        full_em_predictor.set_image(em)
        predictors[f"{pk}_em"] = full_em_predictor

        return Response(status=status.HTTP_200_OK)

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
        mims_bbox = mims_image.canvas_bbox
        # calculate em bbox by finding the min and max x and y of the canvas bbox
        em_bbox = [
            max(0, int(min([m[0] for m in mims_bbox])) - 1000),
            max(0, int(min([m[1] for m in mims_bbox])) - 1000),
            int(max([m[0] for m in mims_bbox])) + 1000,
            int(max([m[1] for m in mims_bbox])) + 1000,
        ]

        if predictor_key not in predictors:
            if image_key != "em":
                image = image_from_im_file(mims_image.file.path, image_key, True)
            else:
                em = np.array(Image.open(mims_image.canvas.images.first().file.path))
                em_cropped = em[em_bbox[1] : em_bbox[3], em_bbox[0] : em_bbox[2]]
                image = em_cropped
            # Convert image to 3 channels if it's single-channel
            if image.ndim == 2:  # If the image is grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

            predictor = SAM2ImagePredictor(sam2_model)
            print(f"Creating predictor for {predictor_key}")
            print(f"Setting image for {predictor_key}")
            predictor.set_image(image)
            print(f"Setting predictor for {predictor_key}")
            predictors[predictor_key] = predictor

        predictor = predictors[predictor_key]
        input_points = np.array(request.data.get("point_coords"))
        input_labels = np.array(request.data.get("point_labels"))
        if image_key == "em":
            input_points = [
                [p[0] - em_bbox[0], p[1] - em_bbox[1]] for p in input_points
            ]
        # print the max and min for each of x and y in the input points
        masks, scores, logits = predictor.predict(
            point_coords=input_points, point_labels=input_labels
        )
        highest_mask = masks[np.argmax(scores)]
        if image_key == "em":
            polygons = mask_to_polygon(highest_mask, translate=[em_bbox[0], em_bbox[1]])
        else:
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
        mims_image.status = "REGISTERING"
        mims_image.save()

        em_shapes = request.data.get("em_shapes")
        mims_shapes = request.data.get("mims_shapes")
        em_points = request.data.get("em_points")
        mims_points = request.data.get("mims_points")
        total_em_points = len(em_points) + len(em_shapes)
        total_mims_points = len(mims_points) + len(mims_shapes)
        if (
            total_em_points == 0
            or total_mims_points == 0
            or total_em_points != total_mims_points
        ):
            return Response(
                {"message": "MIMS image is not ready for registration"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mims_path = Path(mims_image.file.path)
        """reg_loc = os.path.join(mims_path.parent, mims_path.stem, "registration")
        os.makedirs(reg_loc, exist_ok=True)
        with open(os.path.join(reg_loc, "reg_shapes.json"), "w") as shapes_file:
            shapes_file.write(
                json.dumps(
                    {
                        "em_shapes": em_shapes,
                        "mims_shapes": mims_shapes,
                        "em_points": em_points,
                        "mims_points": mims_points,
                    }
                )
            )
        """
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

    @action(detail=True, methods=["get"])
    def existing_registration_data(self, request, pk=None):
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        mims_path = Path(mims_image.file.path)
        reg_loc = os.path.join(mims_path.parent, mims_path.stem, "registration")
        with open(os.path.join(reg_loc, "reg_shapes.json"), "r") as shapes_file:
            reg_data = json.load(shapes_file)
            return Response(reg_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="image.png")
    def image_png(self, request, pk=None):
        """Get a PNG image for a specific species from the MIMS image file"""
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        species = request.query_params.get("species")
        autocontrast = (
            request.query_params.get("autocontrast", "false").lower() == "true"
        )
        binarize = request.query_params.get("binarize", "false").lower() == "true"
        if not species:
            return Response(
                {"error": "species parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            image_data = image_from_im_file(
                mims_image.file.path, species, autocontrast, binarize
            )
            response = HttpResponse(content_type="image/png")
            Image.fromarray(image_data).save(response, format="PNG")
            return response
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def outside_canvas(self, request, pk=None):
        mims_image = get_object_or_404(MIMSImage, pk=pk)
        mims_image.status = "OUTSIDE_CANVAS"
        mims_image.save()
        return Response(
            {"message": "MIMS image is outside the canvas"}, status=status.HTTP_200_OK
        )

    @action(
        detail=True,
        methods=["get"],
        url_path=r"unwarped/(?P<tiff_id>[\w-]+)/(?P<filename>[\w\.-]+)",
    )
    def unwarped(self, request, pk=None, tiff_id=None, filename=None):
        """Return a dewarped version of the MIMS image or EM image crop based on registration_bbox."""
        mims_image = get_object_or_404(MIMSImage, pk=pk)

        # Get the first MimsTiffImage with registration_bbox to determine dimensions
        reference_tiff = mims_image.mims_tiff_images.filter(
            registration_bbox__isnull=False
        ).first()

        if not reference_tiff or not reference_tiff.registration_bbox:
            return Response(
                {"error": "No registration bbox found for this image"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get registration_bbox dimensions
        bbox = reference_tiff.registration_bbox
        # Assuming bbox is in format [[top_left_x, top_left_y], [bottom_right_x, bottom_right_y]]
        width = bbox[1][0] - bbox[0][0]
        height = bbox[1][1] - bbox[0][1]

        # Determine the output size based on the registration_bbox
        output_size = (int(width), int(height))

        if tiff_id == "EM":
            # For EM, crop the canvas image based on the registration_bbox
            em_image = mims_image.image_set.canvas.images.first()
            if not em_image:
                return Response(
                    {"error": "No EM image found for this canvas"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Open the EM image
            em_img = Image.open(em_image.file.path)

            # Crop the EM image to the registration_bbox
            cropped_em = em_img.crop(
                (
                    int(bbox[0][0]),
                    int(bbox[0][1]),  # left, upper
                    int(bbox[1][0]),
                    int(bbox[1][1]),  # right, lower
                )
            )

            # Return the cropped EM image
            response = HttpResponse(content_type="image/png")
            cropped_em.save(response, format="PNG")
            return response
        else:
            # For MIMS images, find the corresponding MimsTiffImage
            tiff_image = mims_image.mims_tiff_images.filter(id=tiff_id).first()

            if not tiff_image:
                return Response(
                    {"error": f"Tiff image with ID {tiff_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Open the tiff image
            tiff_img = Image.open(tiff_image.image.path)

            # Resize the image to match the registration_bbox dimensions
            resized_img = tiff_img.resize(output_size, Image.LANCZOS)

            # Return the resized image
            response = HttpResponse(content_type="image/png")
            resized_img.save(response, format="PNG")
            return response
