from django.apps import AppConfig

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
from pathlib import Path
import cv2

checkpoint = "/Users/chris/Documents/lab/emAnalysis/backend/segment-anything-2/checkpoints/sam2.1_hiera_large.pt"
model_cfg = "configs/sam2.1/sam2.1_hiera_l.yaml"
build_sam2(model_cfg, checkpoint, device="mps")


class MimsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mims"
