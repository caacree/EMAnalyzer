import SimpleITK as sitk
from skimage.transform import SimilarityTransform, warp
from mims.model_utils import load_images_and_bboxes
from mims.services.image_utils import extract_final_digit, image_from_im_file
from mims.models import MIMSImageSet, MimsTiffImage
from mims.services.registration_utils import create_composite_mask
import os
import cv2
import sims
import tifffile
import numpy as np
from PIL import Image
import pandas as pd
from django.conf import settings

media_root = settings.MEDIA_ROOT

possible_12c_names = ["12C", "12C2"]
possible_13c_names = ["13C", "12C 13C"]
possible_15n_names = ["15N 12C", "12C 15N"]
possible_14n_names = ["14N 12C", "12C 14N"]
