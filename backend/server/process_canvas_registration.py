import os
import sys
from pathlib import Path
from django.conf import settings
from django.shortcuts import get_object_or_404
from mims.services.create_overlays import create_registered_overlays
from core.models import Canvas
from mims.models import MIMSImage, MIMSImageSet
from image.models import Image
from mims.tasks import preprocess_mims_image_set, register_images_task
from image.tasks import convert_to_dzi_format
import time


def process_canvas_registration(canvas_id, force_reprocess=False):
    """
    Complete MIMS registration pipeline for a canvas.

    Args:
        canvas_id (str): Canvas UUID
        force_reprocess (bool): If True, reprocess even if files exist

    Returns:
        dict: Status report of processing steps
    """

    print(f"🔍 Processing Canvas: {canvas_id}")
    print("=" * 60)

    # Initialize status tracking
    status = {
        "canvas_id": canvas_id,
        "steps_completed": [],
        "errors": [],
        "files_created": [],
        "processing_time": {},
    }

    try:
        # Step 1: Validate Canvas and Files
        print("📋 Step 1: Validating canvas and required files...")
        start_time = time.time()

        canvas = get_object_or_404(Canvas, id=canvas_id)
        print(f"   ✓ Found canvas: {canvas.name}")

        # Check for EM image
        em_images = canvas.images.all()
        if not em_images.exists():
            raise Exception("No EM images found for this canvas")
        em_image = em_images.first()
        if not os.path.exists(em_image.file.path):
            raise Exception(f"EM image file not found: {em_image.file.path}")
        print(f"   ✓ Found EM image: {em_image.file.name}")

        # Step 2: Create EM DZI if needed
        print("\n🖼️  Step 2: Processing EM image...")
        start_time = time.time()

        if (
            not em_image.dzi_file
            or not os.path.exists(em_image.dzi_file.path)
            or force_reprocess
        ):
            print("   → Creating EM DZI file...")
            convert_to_dzi_format(em_image.id)
            print("   ✓ EM DZI created")
            status["files_created"].append(f"EM DZI: {em_image.dzi_file.name}")
        else:
            print("   ✓ EM DZI already exists")

        status["steps_completed"].append("em_dzi")
        status["processing_time"]["em_dzi"] = time.time() - start_time

        # Step 3: Process each MIMS image set
        # Check for MIMS image sets
        mims_image_sets = MIMSImageSet.objects.filter(canvas=canvas)
        if not mims_image_sets.exists():
            return

        print(f"   ✓ Found {mims_image_sets.count()} MIMS image set(s)")

        # Check for .im files
        total_im_files = 0
        for mims_set in mims_image_sets:
            mims_images = mims_set.mims_images.all()
            for mims_image in mims_images:
                if not os.path.exists(mims_image.file.path):
                    raise Exception(f"MIMS .im file not found: {mims_image.file.path}")
                total_im_files += 1

        print(f"   ✓ Found {total_im_files} .im files")
        status["steps_completed"].append("validation")
        status["processing_time"]["validation"] = time.time() - start_time
        for mims_set in mims_image_sets:
            print(f"\n🧪 Step 3: Processing MIMS Image Set: {mims_set.id}")
            print(f"   Canvas: {canvas.name} | Set ID: {mims_set.id}")

            # Step 3a: Extract isotopes and create composite previews
            print("   → Extracting isotopes and creating composite previews...")
            start_time = time.time()

            # Check if we need to reprocess
            canvas_id_str = str(canvas.id)
            composite_dir = os.path.join(
                settings.MEDIA_ROOT,
                "tmp_images",
                canvas_id_str,
                str(mims_set.id),
                "composites",
                "isotopes",
            )

            needs_preprocessing = (
                (
                    force_reprocess
                    or not os.path.exists(composite_dir)
                    or len([f for f in os.listdir(composite_dir) if f.endswith(".dzi")])
                    == 0
                )
                if os.path.exists(composite_dir)
                else True
            )

            if needs_preprocessing:
                preprocess_mims_image_set(mims_set.id)
                print("   ✓ Isotopes extracted and composite DZI files created")

                # List created files
                if os.path.exists(composite_dir):
                    dzi_files = [
                        f for f in os.listdir(composite_dir) if f.endswith(".dzi")
                    ]
                    for dzi_file in dzi_files:
                        status["files_created"].append(
                            f"Composite DZI: tmp_images/{canvas_id_str}/{mims_set.id}/composites/isotopes/{dzi_file}"
                        )
                    print(f"   📁 Created {len(dzi_files)} composite DZI files")
                else:
                    print("   ⚠️  Composite directory not found after preprocessing")
            else:
                print("   ✓ Isotopes and composites already exist")

            status["processing_time"][f"preprocessing_{mims_set.id}"] = (
                time.time() - start_time
            )

            # Step 3b: Process individual MIMS images (registration)
            mims_images = mims_set.mims_images.all()
            print(f"   → Processing {mims_images.count()} individual MIMS images...")

            for mims_image in mims_images:
                start_time = time.time()

                # Check if registration is needed
                needs_registration = (
                    force_reprocess
                    or mims_image.status != MIMSImage.Status.REGISTERED
                    or not mims_image.mims_tiff_images.exists()
                )

                if needs_registration:
                    # Check if registration info exists
                    if not mims_image.registration_info:
                        reg_shapes_path = (
                            Path(mims_image.file.path).with_suffix("")
                            / "registration"
                            / "reg_shapes.json"
                        )
                        if not reg_shapes_path.exists():
                            print(
                                f"   ⚠️  Skipping {mims_image.file.name}: No registration landmarks found"
                            )
                            status["errors"].append(
                                f"No registration landmarks: {mims_image.file.name}"
                            )
                            continue

                    print(f"   → Registering: {mims_image.file.name}")
                    try:
                        # Run registration (this calls the updated register.py)
                        register_images_task(mims_image.id)

                        # Refresh from database
                        mims_image.refresh_from_db()

                        if mims_image.status == MIMSImage.Status.REGISTERED:
                            print(
                                f"   ✓ Registration completed: {mims_image.file.name}"
                            )

                            # Count registered isotope images in database
                            tiff_count = mims_image.mims_tiff_images.count()
                            status["files_created"].append(
                                f"Registered isotopes: {mims_image.file.name} ({tiff_count} isotopes)"
                            )
                        else:
                            print(
                                f"   ⚠️  Registration may have failed: {mims_image.file.name} (status: {mims_image.status})"
                            )
                            status["errors"].append(
                                f"Registration failed: {mims_image.file.name}"
                            )

                    except Exception as e:
                        print(
                            f"   ❌ Registration error for {mims_image.file.name}: {str(e)}"
                        )
                        status["errors"].append(
                            f"Registration error {mims_image.file.name}: {str(e)}"
                        )
                        raise e

                else:
                    print(f"   ✓ Already registered: {mims_image.file.name}")

                status["processing_time"][f"registration_{mims_image.id}"] = (
                    time.time() - start_time
                )
                # create registered overlay
                create_registered_overlays(mims_set)

        status["steps_completed"].append("mims_processing")

        # Step 4: Final Status Report
        print("\n" + "=" * 60)
        print("📊 PROCESSING COMPLETE")
        print("=" * 60)

        print(f"Canvas ID: {canvas_id}")
        print(f"Canvas Name: {canvas.name}")
        print(f"Steps Completed: {', '.join(status['steps_completed'])}")
        print(f"Files Created: {len(status['files_created'])}")
        print(f"Errors: {len(status['errors'])}")

        if status["files_created"]:
            print("\n📁 Files Created:")
            for file_path in status["files_created"]:
                print(f"   • {file_path}")

        if status["errors"]:
            print("\n❌ Errors:")
            for error in status["errors"]:
                print(f"   • {error}")

        print(f"\n⏱️  Processing Times:")
        total_time = sum(status["processing_time"].values())
        for step, duration in status["processing_time"].items():
            print(f"   • {step}: {duration:.2f}s")
        print(f"   • TOTAL: {total_time:.2f}s")

        return status

    except Exception as e:
        raise e


def list_canvas_files(canvas_id):
    """
    Utility function to list all files associated with a canvas.
    """
    print(f"📋 Files for Canvas: {canvas_id}")
    print("=" * 50)

    try:
        canvas = get_object_or_404(Canvas, id=canvas_id)

        # EM Images
        print("🖼️  EM Images:")
        em_images = canvas.images.all()
        for em_image in em_images:
            print(f"   • {em_image.file.name}")
            if em_image.dzi_file:
                print(f"     → DZI: {em_image.dzi_file.name}")

        # MIMS Image Sets
        mims_sets = MIMSImageSet.objects.filter(canvas=canvas)
        print(f"\n🧪 MIMS Image Sets ({mims_sets.count()}):")

        for mims_set in mims_sets:
            print(f"   Set ID: {mims_set.id}")

            # Individual MIMS images
            mims_images = mims_set.mims_images.all()
            print(f"   • MIMS Images ({mims_images.count()}):")
            for mims_image in mims_images:
                print(f"     - {mims_image.file.name} (Status: {mims_image.status})")

                # Registered isotope images
                tiff_images = mims_image.mims_tiff_images.all()
                if tiff_images.exists():
                    print(f"       → Registered isotopes: {tiff_images.count()}")

            # Composite files
            canvas_id_str = str(canvas.id)
            composite_dir = os.path.join(
                settings.MEDIA_ROOT,
                "tmp_images",
                canvas_id_str,
                str(mims_set.id),
                "composites",
                "isotopes",
            )

            if os.path.exists(composite_dir):
                dzi_files = [f for f in os.listdir(composite_dir) if f.endswith(".dzi")]
                print(f"   • Composite DZI files: {len(dzi_files)}")
                for dzi_file in dzi_files:
                    print(f"     - {dzi_file}")
            else:
                print(f"   • Composite directory not found: {composite_dir}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


# Example usage for Jupyter notebook:
"""
# To process a canvas:
status = process_canvas_registration("your-canvas-id-here")

# To force reprocess everything:
status = process_canvas_registration("your-canvas-id-here", force_reprocess=True)

# To list files for a canvas:
list_canvas_files("your-canvas-id-here")
"""
