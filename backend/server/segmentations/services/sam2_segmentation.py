"""MobileSAM segmentation with tiled processing for large images."""

import logging
import time
import traceback

import numpy as np
import torch
from mobile_sam import sam_model_registry, SamAutomaticMaskGenerator, SamPredictor

logger = logging.getLogger(__name__)


def run_sam2_segmentation(
    image_array: np.ndarray, tile_size: int = 2048, overlap: int = 256
) -> np.ndarray:
    """
    Run MobileSAM automatic segmentation on an image with tiled processing for large images.

    For images larger than tile_size, divides into overlapping tiles, processes each tile
    with MobileSAM, and reconstructs the full mask. Maintains full resolution throughout.

    Args:
        image_array: Input image as numpy array (grayscale uint8)
        tile_size: Size of tiles to process (default 2048)
        overlap: Overlap between tiles in pixels (default 256)

    Returns:
        Combined mask image as uint8 or uint16 where each detected object has a unique value
    """
    import os

    print(f"\n{'='*60}")
    print(f"[MobileSAM] Function entered, image shape: {image_array.shape}")
    print(f"{'='*60}\n")

    # Force PyTorch to use MPS if available
    if torch.backends.mps.is_available():
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        logger.info("Enabled MPS fallback for PyTorch")

    try:
        print("[MobileSAM] Starting segmentation...")

        # Get original dimensions
        print("[MobileSAM] Getting image dimensions...")
        if len(image_array.shape) == 2:
            height, width = image_array.shape
            is_grayscale = True
        else:
            height, width = image_array.shape[:2]
            is_grayscale = False
        print(f"[MobileSAM] Image: {width}x{height}, grayscale={is_grayscale}")

        # Get device (prefer CUDA, then MPS, then CPU)
        # MobileSAM is lightweight and works well on MPS
        print("[MobileSAM] Checking device availability...")
        if torch.cuda.is_available():
            device = torch.device("cuda")
            print("[MobileSAM] Using CUDA GPU")
        elif torch.backends.mps.is_available():
            device = torch.device("mps")
            # MPS doesn't support float64, so set default to float32
            torch.set_default_dtype(torch.float32)
            print("[MobileSAM] Using MPS (Apple Silicon GPU) with float32")
        else:
            device = torch.device("cpu")
            print("[MobileSAM] Using CPU")

        # Build MobileSAM model
        model_type = "vit_t"  # MobileSAM uses ViT-Tiny
        checkpoint = (
            "/Users/chris/Documents/lab/emAnalysis/backend/server/mobile_sam.pt"
        )

        print(f"[MobileSAM] Loading model from {checkpoint}...")
        mobile_sam = sam_model_registry[model_type](checkpoint=checkpoint)
        print(f"[MobileSAM] Model loaded, moving to device: {device}...")
        mobile_sam.to(device=device)

        # For MPS, we need to patch the model to handle float32
        if device.type == "mps":
            print("[MobileSAM] Patching model for MPS float32 compatibility...")
            mobile_sam = mobile_sam.float()  # Ensure model is float32

        print(f"[MobileSAM] Model on device, setting to eval mode...")
        mobile_sam.eval()
        print(f"[MobileSAM] Model ready!")

        # Adjust tile size and parameters for MPS to avoid OOM
        if device.type == "mps":
            tile_size = 1024  # Smaller tiles for MPS
            overlap = 128
            points_per_side_single = 16  # Fewer points for MPS
            points_per_side_tile = 12
            print(f"[MobileSAM] Using MPS-optimized settings: tile_size={tile_size}, points={points_per_side_tile}")
        else:
            points_per_side_single = 32
            points_per_side_tile = 24

        # Check if tiling is needed
        needs_tiling = width > tile_size or height > tile_size
        print(f"[MobileSAM] Needs tiling: {needs_tiling} (image {width}x{height}, tile size {tile_size})")

        if not needs_tiling:
            # Small image - process directly
            print("[MobileSAM] Image fits in single tile, processing directly")
            logger.info("Image fits in single tile, processing directly")
            # Create mask generator for single image
            mask_generator = SamAutomaticMaskGenerator(
                model=mobile_sam,
                points_per_side=points_per_side_single,
                pred_iou_thresh=0.8,
                stability_score_thresh=0.92,
                crop_n_layers=0,
                min_mask_region_area=100,
            )
            return _process_mobile_sam_single_image(image_array, mask_generator, device)

        # Large image - use tiled processing
        print(f"[MobileSAM] Large image - using tiled processing ({tile_size}x{tile_size} with {overlap}px overlap)")

        # Calculate tile grid
        stride = tile_size - overlap
        num_tiles_x = int(np.ceil((width - overlap) / stride))
        num_tiles_y = int(np.ceil((height - overlap) / stride))
        print(f"[MobileSAM] Will process {num_tiles_x * num_tiles_y} tiles ({num_tiles_x}x{num_tiles_y} grid)")

        # Initialize output mask
        print(f"[MobileSAM] Initializing output mask ({height}x{width})...")
        combined_mask = np.zeros((height, width), dtype=np.uint32)
        next_label = 1
        print(f"[MobileSAM] Output mask initialized, starting tile processing...")

        # Track timing for progress estimation
        total_tiles = num_tiles_x * num_tiles_y
        tiles_processed = 0
        start_time = time.time()
        tile_times = []
        last_reported_pct = -1

        # Process each tile
        for ty in range(num_tiles_y):
            for tx in range(num_tiles_x):
                tile_start_time = time.time()
                tiles_processed += 1

                if tiles_processed == 1:
                    print(f"[MobileSAM] Starting first tile ({ty}, {tx})...")

                # Calculate tile boundaries
                y_start = ty * stride
                x_start = tx * stride
                y_end = min(y_start + tile_size, height)
                x_end = min(x_start + tile_size, width)

                # Extract tile
                if is_grayscale:
                    tile = image_array[y_start:y_end, x_start:x_end]
                else:
                    tile = image_array[y_start:y_end, x_start:x_end, :]

                if tiles_processed == 1:
                    print(f"[MobileSAM] Extracted tile shape: {tile.shape}")
                    print(f"[MobileSAM] Creating mask generator for first tile...")

                # Create fresh mask generator for this tile to avoid state issues
                # Use fewer points for tiles to reduce memory usage
                tile_mask_generator = SamAutomaticMaskGenerator(
                    model=mobile_sam,
                    points_per_side=points_per_side_tile,
                    pred_iou_thresh=0.8,
                    stability_score_thresh=0.92,
                    crop_n_layers=0,
                    min_mask_region_area=50,  # Reduced from 100 for smaller tiles
                )

                if tiles_processed == 1:
                    print(f"[MobileSAM] Mask generator created, processing first tile...")

                # Process tile with MobileSAM
                tile_mask = _process_mobile_sam_single_image(tile, tile_mask_generator, device)

                if tiles_processed == 1:
                    print(f"[MobileSAM] First tile processed! Result shape: {tile_mask.shape}")

                # Clean up to free memory
                del tile_mask_generator
                if device.type == "mps":
                    torch.mps.empty_cache()
                import gc
                gc.collect()

                # Record tile processing time
                tile_elapsed = time.time() - tile_start_time
                tile_times.append(tile_elapsed)

                # Log progress at key milestones: after first tile, then every 20%
                progress_pct = (tiles_processed / total_tiles) * 100
                current_milestone = int(progress_pct / 20) * 20

                should_log = (tiles_processed == 1) or (
                    current_milestone > last_reported_pct
                    and current_milestone % 20 == 0
                )

                if should_log:
                    elapsed_time = time.time() - start_time
                    elapsed_min = elapsed_time / 60

                    if tiles_processed > 1:
                        avg_time_per_tile = sum(tile_times) / len(tile_times)
                        remaining_tiles = total_tiles - tiles_processed
                        est_remaining_sec = avg_time_per_tile * remaining_tiles
                        est_remaining_min = est_remaining_sec / 60
                        logger.info(
                            f"[MobileSAM] Tile {tiles_processed}/{total_tiles}, "
                            f"elapsed: {elapsed_min:.1f}min, est. remaining: {est_remaining_min:.1f}min"
                        )
                    else:
                        logger.info(
                            f"[MobileSAM] Tile {tiles_processed}/{total_tiles}, "
                            f"elapsed: {elapsed_min:.1f}min"
                        )

                    last_reported_pct = current_milestone

                # Relabel to avoid conflicts with existing labels
                unique_labels = np.unique(tile_mask)
                unique_labels = unique_labels[unique_labels > 0]

                if len(unique_labels) > 0:
                    # Create relabeling map
                    relabel_map = np.zeros(tile_mask.max() + 1, dtype=np.uint32)
                    for old_label in unique_labels:
                        relabel_map[old_label] = next_label
                        next_label += 1

                    # Relabel tile mask
                    tile_mask_relabeled = relabel_map[tile_mask]

                    # Calculate blending region (use center of overlap)
                    # For overlapping regions, only keep objects whose center is in this tile
                    blend_y_start = overlap // 2 if ty > 0 else 0
                    blend_x_start = overlap // 2 if tx > 0 else 0
                    blend_y_end = (
                        tile_mask_relabeled.shape[0] - (overlap // 2)
                        if ty < num_tiles_y - 1
                        else tile_mask_relabeled.shape[0]
                    )
                    blend_x_end = (
                        tile_mask_relabeled.shape[1] - (overlap // 2)
                        if tx < num_tiles_x - 1
                        else tile_mask_relabeled.shape[1]
                    )

                    # Extract the region to keep
                    tile_region = tile_mask_relabeled[
                        blend_y_start:blend_y_end, blend_x_start:blend_x_end
                    ]

                    # Place in output
                    out_y_start = y_start + blend_y_start
                    out_x_start = x_start + blend_x_start
                    out_y_end = out_y_start + tile_region.shape[0]
                    out_x_end = out_x_start + tile_region.shape[1]

                    # Only write where output is still 0 (no overlap)
                    output_region = combined_mask[
                        out_y_start:out_y_end, out_x_start:out_x_end
                    ]
                    mask_to_write = tile_region > 0
                    output_region[mask_to_write] = tile_region[mask_to_write]

        # Count total objects
        total_objects = len(np.unique(combined_mask)) - 1  # Exclude 0

        # Convert to optimal dtype
        if total_objects <= 255:
            combined_mask = combined_mask.astype(np.uint8)
        elif total_objects <= 65535:
            combined_mask = combined_mask.astype(np.uint16)

        # Report final statistics
        total_time = time.time() - start_time
        avg_time_per_tile = sum(tile_times) / len(tile_times) if tile_times else 0
        logger.info(
            f"MobileSAM tiled segmentation complete: {total_objects} total objects, "
            f"output shape {combined_mask.shape}, "
            f"processed {total_tiles} tiles in {total_time:.1f}s "
            f"(avg {avg_time_per_tile:.1f}s/tile)"
        )
        return combined_mask

    except Exception as e:
        logger.error(f"Error running MobileSAM segmentation: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def _process_mobile_sam_single_image(
    image_array: np.ndarray, mask_generator, device: torch.device
) -> np.ndarray:
    """
    Process a single image (or tile) with MobileSAM.

    Args:
        image_array: Input image as numpy array (grayscale or RGB uint8)
        mask_generator: SamAutomaticMaskGenerator instance
        device: Torch device being used

    Returns:
        Combined mask as uint16 where each object has a unique label
    """
    # Ensure image is in correct format (HWC uint8 RGB)
    if len(image_array.shape) == 2:
        # Grayscale to RGB
        image_rgb = np.stack([image_array, image_array, image_array], axis=-1)
    else:
        image_rgb = image_array

    if image_rgb.dtype != np.uint8:
        # Normalize to 0-255 uint8
        if image_rgb.max() <= 1:
            image_rgb = (image_rgb * 255).astype(np.uint8)
        else:
            image_rgb = image_rgb.astype(np.uint8)

    # For MPS devices, monkey-patch torch.as_tensor to force float32
    device_type = mask_generator.predictor.device.type if hasattr(mask_generator, 'predictor') else None
    if device_type == "mps":
        original_as_tensor = torch.as_tensor
        def as_tensor_float32(data, *args, **kwargs):
            # Convert numpy float64 to float32 for MPS
            if isinstance(data, np.ndarray) and data.dtype == np.float64:
                data = data.astype(np.float32)
            return original_as_tensor(data, *args, **kwargs)
        torch.as_tensor = as_tensor_float32

    try:
        # Generate masks
        masks = mask_generator.generate(image_rgb)
    finally:
        # Restore original torch.as_tensor if we patched it
        if device_type == "mps":
            torch.as_tensor = original_as_tensor

    # Create combined mask image
    h, w = image_rgb.shape[:2]
    combined_mask = np.zeros((h, w), dtype=np.uint16)

    # Sort masks by area (largest first) to prioritize larger objects
    masks = sorted(masks, key=lambda x: x["area"], reverse=True)

    # Assign each mask a unique label
    for idx, mask_data in enumerate(masks, start=1):
        mask = mask_data["segmentation"]
        # Only assign where not already assigned (avoid overlap)
        combined_mask[mask & (combined_mask == 0)] = idx

    # Clean up GPU memory for MPS
    if device.type == "mps":
        torch.mps.empty_cache()
        import gc
        gc.collect()

    return combined_mask
