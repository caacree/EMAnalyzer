import cv2
import numpy as np


def test_mask_iou(mask1, mask2, padding=None):
    if (
        padding is None
        or (mask1.shape[0] < mask2.shape[0])
        or (mask1.shape[1] < mask2.shape[1])
    ):
        padding = max(mask2.shape[0], mask2.shape[1])
    mask1_padded = np.pad(mask1, padding)
    _, _, _, max_loc = cv2.minMaxLoc(
        cv2.matchTemplate(mask1_padded, mask2, cv2.TM_CCOEFF_NORMED)
    )
    max_loc = (max_loc[0] - padding, max_loc[1] - padding)
    mask1_y_start = padding + max_loc[1]
    mask1_y_end = mask1_y_start + mask2.shape[0]
    mask1_x_start = padding + max_loc[0]
    mask1_x_end = mask1_x_start + mask2.shape[1]

    mask1_translated = mask1_padded[
        mask1_y_start:mask1_y_end, mask1_x_start:mask1_x_end
    ]
    return iou(mask1_translated, mask2), max_loc


def iou(mask1, mask2):
    intersection = np.logical_and(mask1, mask2)
    union = np.logical_or(mask1, mask2)
    return np.sum(intersection) / np.sum(union)
