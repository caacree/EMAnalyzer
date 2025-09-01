import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import os
from pathlib import Path
import cv2
from django.conf import settings


def _save_debug_overlay(mims_img, geom, patch, iso_name):
    """
    Saves a debug image of a single patch overlaid on its corresponding EM crop.

    The overlay is magenta with 40% opacity. This provides a clear visual
    check of the alignment for each patch before it's placed in the mosaic.
    """
    # --- 1. Load and crop the full-resolution EM image ---
    em_path = mims_img.image_set.canvas.images.first().file.path
    em_full = np.array(Image.open(em_path))
    x0, y0, x1, y1 = geom["bbox"]
    em_crop = em_full[y0:y1, x0:x1]

    # --- 2. Prepare the magenta overlay from the patch ---
    # Resize patch to match the EM crop dimensions for overlay
    patch_resized = cv2.resize(
        patch, (em_crop.shape[1], em_crop.shape[0]), interpolation=cv2.INTER_NEAREST
    )

    # Normalize patch data to [0, 1] for color mapping
    patch_norm = patch_resized.astype(np.float32)
    p99 = np.percentile(patch_norm, 99)  # Use 99th percentile for better contrast
    if p99 > 0:
        patch_norm = np.clip(patch_norm, 0, p99) / p99
    else:  # Handle blank patches
        patch_norm = np.zeros_like(patch_norm)

    # Create an RGB image for the magenta overlay
    mag_overlay = np.zeros(em_crop.shape + (3,), dtype=np.float32)
    mag_overlay[..., 0] = patch_norm  # Red channel
    mag_overlay[..., 2] = patch_norm  # Blue channel

    # --- 3. Create and save the figure ---
    fig, ax = plt.subplots()
    ax.imshow(em_crop, cmap="gray")
    ax.imshow(mag_overlay, alpha=0.4)
    ax.axis("off")
    ax.set_title(f"Debug: {mims_img.name} ({iso_name})")

    # Define a unique path for the debug image
    # NOTE: Adjust the base path to a directory that exists!
    debug_dir = Path(settings.MEDIA_ROOT) / "debug_patches"
    os.makedirs(debug_dir, exist_ok=True)
    out_path = debug_dir / f"overlay_{mims_img.id}_{iso_name}.png"

    plt.savefig(out_path, bbox_inches="tight", pad_inches=0)
    plt.close(fig)  # Close the figure to save memory
    print(f"✓ Saved debug overlay to {out_path}")
