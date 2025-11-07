from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.files.base import ContentFile
import logging
import traceback
import pyvips
import os
import numpy as np
from PIL import Image
import io
import time

from .models import SegmentationFile
from .services import (
    convert_to_compressed_png,
    process_segmentation_file_with_progress,
    apply_sobel_filter,
    run_sam2_segmentation,  # Now using MobileSAM - much faster!
)

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_segmentation_upload_async(self, segmentation_file_id):
    """
    Async task for processing newly uploaded segmentation files.
    Generates DZI file and compressed PNG from raw upload.
    """
    try:
        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"STARTING SEGMENTATION UPLOAD PROCESSING: {segmentation_file_id}")
        print(f"{'='*60}\n")

        # Get the segmentation file
        seg_file = SegmentationFile.objects.get(id=segmentation_file_id)

        # Update task ID
        seg_file.processing_info = seg_file.processing_info or {}
        seg_file.processing_info["task_id"] = self.request.id
        seg_file.save(update_fields=["processing_info"])

        # Update progress
        seg_file.progress = 10
        seg_file.progress_message = "Loading raw image..."
        seg_file.save(update_fields=["progress", "progress_message"])

        # Step 1: Generate DZI from raw file
        step_start = time.time()
        print(f"[STEP 1] Loading raw image with pyvips...")
        raw_path = seg_file.raw_file.path
        img = pyvips.Image.new_from_file(raw_path, access="sequential")
        print(f"[STEP 1] ✓ Loaded image ({img.width}x{img.height}) in {time.time() - step_start:.2f}s")

        # Define DZI save path
        dzi_save_path = os.path.join(
            settings.MEDIA_ROOT,
            "tmp_images",
            str(seg_file.canvas.id),
            "segmentations",
            str(seg_file.id)
        )

        # Ensure directory exists
        os.makedirs(dzi_save_path, exist_ok=True)

        # Construct the ID URL for IIIF3
        id_url = f"http://localhost:8000{settings.MEDIA_URL}{os.path.join('tmp_images', str(seg_file.canvas.id), 'segmentations')}"

        seg_file.progress = 30
        seg_file.progress_message = "Generating DZI tiles..."
        seg_file.save(update_fields=["progress", "progress_message"])

        # Check if image is small (≤512x512) and adjust DZI parameters
        step_start = time.time()
        print(f"[STEP 1] Generating DZI tiles for original image...")
        if img.width <= 512 and img.height <= 512:
            img.dzsave(
                dzi_save_path,
                id=id_url,
                tile_size=512,
                depth="one",
                layout=pyvips.enums.ForeignDzLayout.IIIF3,
            )
        else:
            img.dzsave(
                dzi_save_path,
                id=id_url,
                layout=pyvips.enums.ForeignDzLayout.IIIF3,
            )
        print(f"[STEP 1] ✓ Generated original DZI in {time.time() - step_start:.2f}s")

        # Update dzi_file field
        seg_file.dzi_file.name = os.path.join(
            "tmp_images",
            str(seg_file.canvas.id),
            "segmentations",
            str(seg_file.id),
            "info.json"
        )

        seg_file.progress = 60
        seg_file.progress_message = "DZI generated, creating compressed PNG..."
        seg_file.save(update_fields=["dzi_file", "progress", "progress_message"])

        # Step 2: Generate compressed PNG
        step_start = time.time()
        print(f"\n[STEP 2] Creating compressed PNG...")
        # Re-open the raw file for PNG conversion
        # Create a file-like object
        class RawFileWrapper:
            def __init__(self, file_path, name):
                self.file_path = file_path
                self.name = name

            def read(self):
                with open(self.file_path, 'rb') as f:
                    return f.read()

        raw_file_wrapper = RawFileWrapper(raw_path, os.path.basename(raw_path))
        compressed_png = convert_to_compressed_png(raw_file_wrapper, seg_file.upload_type)
        print(f"[STEP 2] ✓ Created compressed PNG in {time.time() - step_start:.2f}s")

        # Save compressed PNG
        seg_file.file = compressed_png
        seg_file.progress = 60
        seg_file.progress_message = "Compressed PNG created, processing derivatives..."
        seg_file.save(update_fields=["file", "progress", "progress_message"])

        # Load image array before deleting raw file (needed for Sobel/SAM2)
        # IMPORTANT: Load from the compressed uint8 PNG (not raw file) to save memory
        img_array = None
        if seg_file.upload_type == SegmentationFile.UploadType.PROBABILITY:
            step_start = time.time()
            print(f"\n[STEP 2.5] Loading uint8 image array from compressed PNG for derivative processing...")
            # Load from the compressed PNG we just saved (uint8, 4x smaller than raw)
            compressed_png_path = seg_file.file.path
            img_array = np.array(Image.open(compressed_png_path))
            print(f"[STEP 2.5] ✓ Loaded uint8 image array ({img_array.shape}, {img_array.dtype}) in {time.time() - step_start:.2f}s")
            print(f"[STEP 2.5]   Memory usage: {img_array.nbytes / 1024 / 1024:.2f} MB")

        # Delete the raw file to save space (it's no longer needed)
        print(f"\n[CLEANUP] Deleting raw file to save space...")
        cleanup_start = time.time()
        if seg_file.raw_file and os.path.exists(raw_path):
            try:
                os.remove(raw_path)
                # Try to remove the raw directory if it's empty
                raw_dir = os.path.dirname(raw_path)
                if os.path.exists(raw_dir) and not os.listdir(raw_dir):
                    os.rmdir(raw_dir)
                print(f"[CLEANUP] ✓ Deleted raw file in {time.time() - cleanup_start:.2f}s")
            except Exception as e:
                logger.warning(f"Failed to delete raw file: {str(e)}")
                print(f"[CLEANUP] ⚠ Failed to delete raw file: {str(e)}")

        # Only process Sobel and SAM2 for probability maps
        if seg_file.upload_type == SegmentationFile.UploadType.PROBABILITY:
            print(f"\n[PROBABILITY MAP] Processing derivative images...")

            # Step 3: Generate Sobel edge detection
            seg_file.progress = 65
            seg_file.progress_message = "Applying Sobel edge detection..."
            seg_file.save(update_fields=["progress", "progress_message"])

            # Apply Sobel filter (using pre-loaded image array)
            step_start = time.time()
            print(f"[STEP 3] Applying Sobel edge detection...")
            sobel_edges = apply_sobel_filter(img_array)
            print(f"[STEP 3] ✓ Applied Sobel filter in {time.time() - step_start:.2f}s")

            # Save Sobel image as PNG
            step_start = time.time()
            print(f"[STEP 3] Saving Sobel edges as PNG...")
            sobel_dir = os.path.join(
                settings.MEDIA_ROOT,
                "tmp_images",
                str(seg_file.canvas.id),
                "segmentations",
                str(seg_file.id),
                "sobel"
            )
            os.makedirs(sobel_dir, exist_ok=True)
            sobel_png_path = os.path.join(sobel_dir, "edges.png")
            Image.fromarray(sobel_edges).save(sobel_png_path, format='PNG', compress_level=6)
            print(f"[STEP 3] ✓ Saved Sobel PNG in {time.time() - step_start:.2f}s")

            # Generate DZI for Sobel
            seg_file.progress = 70
            seg_file.progress_message = "Generating Sobel DZI tiles..."
            seg_file.save(update_fields=["progress", "progress_message"])

            step_start = time.time()
            print(f"[STEP 3] Generating DZI tiles for Sobel edges...")
            sobel_img = pyvips.Image.new_from_file(sobel_png_path, access="sequential")

            if sobel_img.width <= 512 and sobel_img.height <= 512:
                sobel_img.dzsave(
                    sobel_dir,
                    id=id_url,
                    tile_size=512,
                    depth="one",
                    layout=pyvips.enums.ForeignDzLayout.IIIF3,
                )
            else:
                sobel_img.dzsave(
                    sobel_dir,
                    id=id_url,
                    layout=pyvips.enums.ForeignDzLayout.IIIF3,
                )
            print(f"[STEP 3] ✓ Generated Sobel DZI in {time.time() - step_start:.2f}s")

            # Update sobel_dzi_file field
            seg_file.sobel_dzi_file.name = os.path.join(
                "tmp_images",
                str(seg_file.canvas.id),
                "segmentations",
                str(seg_file.id),
                "sobel",
                "info.json"
            )
            seg_file.save(update_fields=["sobel_dzi_file"])

            # Step 4: Generate MobileSAM segmentation
            seg_file.progress = 75
            seg_file.progress_message = "Running MobileSAM segmentation (this may take a while)..."
            seg_file.save(update_fields=["progress", "progress_message"])

            # Run MobileSAM (using pre-loaded image array)
            step_start = time.time()
            print(f"\n[STEP 4] Running MobileSAM segmentation (this may take a while)...")
            print(f"[STEP 4] About to call run_sam2_segmentation with array shape: {img_array.shape}, dtype: {img_array.dtype}")
            sam2_masks = run_sam2_segmentation(img_array)
            print(f"[STEP 4] ✓ MobileSAM segmentation complete in {time.time() - step_start:.2f}s")

            # Save MobileSAM masks as PNG
            step_start = time.time()
            print(f"[STEP 4] Saving MobileSAM masks as PNG...")
            sam2_dir = os.path.join(
                settings.MEDIA_ROOT,
                "tmp_images",
                str(seg_file.canvas.id),
                "segmentations",
                str(seg_file.id),
                "sam2"
            )
            os.makedirs(sam2_dir, exist_ok=True)
            sam2_png_path = os.path.join(sam2_dir, "masks.png")
            Image.fromarray(sam2_masks).save(sam2_png_path, format='PNG', compress_level=6)
            print(f"[STEP 4] ✓ Saved MobileSAM PNG in {time.time() - step_start:.2f}s")

            # Generate DZI for MobileSAM
            seg_file.progress = 90
            seg_file.progress_message = "Generating MobileSAM DZI tiles..."
            seg_file.save(update_fields=["progress", "progress_message"])

            step_start = time.time()
            print(f"[STEP 4] Generating DZI tiles for MobileSAM masks...")
            sam2_img = pyvips.Image.new_from_file(sam2_png_path, access="sequential")

            if sam2_img.width <= 512 and sam2_img.height <= 512:
                sam2_img.dzsave(
                    sam2_dir,
                    id=id_url,
                    tile_size=512,
                    depth="one",
                    layout=pyvips.enums.ForeignDzLayout.IIIF3,
                )
            else:
                sam2_img.dzsave(
                    sam2_dir,
                    id=id_url,
                    layout=pyvips.enums.ForeignDzLayout.IIIF3,
                )
            print(f"[STEP 4] ✓ Generated MobileSAM DZI in {time.time() - step_start:.2f}s")

            # Update sam2_dzi_file field (keeping same field name for backward compatibility)
            seg_file.sam2_dzi_file.name = os.path.join(
                "tmp_images",
                str(seg_file.canvas.id),
                "segmentations",
                str(seg_file.id),
                "sam2",
                "info.json"
            )
            seg_file.save(update_fields=["sam2_dzi_file"])

        # Mark as completed
        seg_file.status = SegmentationFile.Status.COMPLETED
        seg_file.progress = 100
        seg_file.progress_message = "Upload processing complete"
        seg_file.save(update_fields=["status", "progress", "progress_message"])

        total_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"✓ COMPLETED SEGMENTATION UPLOAD PROCESSING")
        print(f"  Total time: {total_time:.2f}s")
        print(f"{'='*60}\n")

        logger.info(f"Successfully processed segmentation upload {segmentation_file_id}")
        return {"success": True, "segmentation_file_id": str(segmentation_file_id)}

    except SoftTimeLimitExceeded:
        logger.error(f"Task timed out for segmentation file {segmentation_file_id}")

        try:
            seg_file = SegmentationFile.objects.get(id=segmentation_file_id)
            seg_file.status = SegmentationFile.Status.FAILED
            seg_file.progress_message = "Processing timed out"
            seg_file.processing_info = {"error": "Task exceeded time limit"}
            seg_file.save()
        except:
            pass

        return {"success": False, "error": "Processing timed out"}

    except Exception as e:
        logger.error(f"Error in async upload processing: {str(e)}")
        logger.error(traceback.format_exc())

        try:
            seg_file = SegmentationFile.objects.get(id=segmentation_file_id)
            seg_file.status = SegmentationFile.Status.FAILED
            seg_file.progress_message = f"Error: {str(e)}"
            seg_file.processing_info = {"error": str(e), "traceback": traceback.format_exc()}
            seg_file.save()
        except:
            pass

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True)
def process_segmentation_file_async(self, segmentation_file_id):
    """
    Async task for processing segmentation files with progress tracking.
    """
    try:
        # Get the segmentation file
        seg_file = SegmentationFile.objects.get(id=segmentation_file_id)

        # Update task ID in the model for tracking
        seg_file.processing_info = seg_file.processing_info or {}
        seg_file.processing_info["task_id"] = self.request.id
        seg_file.save(update_fields=["processing_info"])

        # Process with progress tracking
        success = process_segmentation_file_with_progress(segmentation_file_id, self)

        if not success:
            # Retry on failure
            raise self.retry(countdown=60)  # Retry after 60 seconds

        return {"success": True, "segmentation_file_id": str(segmentation_file_id)}

    except SoftTimeLimitExceeded:
        logger.error(f"Task timed out for segmentation file {segmentation_file_id}")

        try:
            seg_file = SegmentationFile.objects.get(id=segmentation_file_id)
            seg_file.status = SegmentationFile.Status.FAILED
            seg_file.progress_message = "Processing timed out"
            seg_file.processing_info = {"error": "Task exceeded time limit"}
            seg_file.save()
        except:
            pass

        return {"success": False, "error": "Processing timed out"}

    except Exception as e:
        logger.error(f"Error in async segmentation processing: {str(e)}")
        logger.error(traceback.format_exc())

        try:
            seg_file = SegmentationFile.objects.get(id=segmentation_file_id)
            seg_file.status = SegmentationFile.Status.FAILED
            seg_file.progress_message = f"Error: {str(e)}"
            seg_file.processing_info = {"error": str(e)}
            seg_file.save()
        except:
            pass

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
