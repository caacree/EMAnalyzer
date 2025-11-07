import os
import numpy as np
import pyvips
from django.conf import settings
from mims.models import MIMSImage, MIMSImageSet, Isotope, MIMSOverlay
from mims.model_utils import get_concatenated_image


def create_registered_overlays(image_set):
    """
    Create composite overlay images when an image set transitions to REGISTERED status.
    This stitches together MimsTiffImages from all registered images into canvas-sized composites.
    """
    print(f"Creating registered overlays for image set {image_set.id}")

    # Get all registered images in the set
    registered_images = image_set.mims_images.filter(status=MIMSImage.Status.REGISTERED)
    if not registered_images.exists():
        print("No registered images found")
        return

    # Get canvas dimensions from the EM image
    canvas = image_set.canvas
    em_image = canvas.images.first()
    if not em_image:
        print("No EM image found for canvas")
        return

    from PIL import Image

    em_img = Image.open(em_image.file.path)
    canvas_width, canvas_height = em_img.size

    # Get all isotopes from registered images
    isotopes_set = set()
    for img in registered_images:
        for tiff_image in img.mims_tiff_images.all():
            isotopes_set.add(tiff_image.name)

    isotopes = list(isotopes_set)

    # Add ratio isotopes if base isotopes exist
    possible_12c_names = ["12C", "12C2"]
    possible_13c_names = ["13C", "12C 13C"]
    possible_15n_names = ["15N 12C", "12C 15N"]
    possible_14n_names = ["14N 12C", "12C 14N"]

    species_12c = next((name for name in possible_12c_names if name in isotopes), None)
    species_13c = next((name for name in possible_13c_names if name in isotopes), None)
    if species_12c and species_13c:
        isotopes.append("13C12C_ratio")

    species_15n = next((name for name in possible_15n_names if name in isotopes), None)
    species_14n = next((name for name in possible_14n_names if name in isotopes), None)
    if species_15n and species_14n:
        isotopes.append("15N14N_ratio")

    # Create composite overlays for each isotope
    canvas_id = str(image_set.canvas.id)
    relative_dir = os.path.join("tmp_images", canvas_id, str(image_set.id), "overlays")
    output_dir = os.path.join(settings.MEDIA_ROOT, relative_dir)
    os.makedirs(output_dir, exist_ok=True)

    for isotope in isotopes:
        print(f"Processing isotope: {isotope}")

        try:
            # Create canvas-sized composite image for this isotope
            composite_img = create_isotope_composite(
                registered_images, isotope, canvas_width, canvas_height
            )

            if composite_img is None:
                print(f"No data found for isotope {isotope}")
                continue

            # Save as compressed PNG
            comp_path = os.path.join(output_dir, isotope + ".png")
            Image.fromarray(composite_img).save(comp_path, format='PNG', optimize=True, compress_level=6)

            # Convert to pyvips image
            img = pyvips.Image.new_from_array(composite_img)

            # Create DZI file
            id_url = os.path.join("http://localhost:8000/media", relative_dir)

            if img.width <= 512 and img.height <= 512:
                img.dzsave(
                    os.path.join(output_dir, isotope + ".dzi"),
                    id=id_url,
                    tile_size=512,
                    depth="one",
                    layout=pyvips.enums.ForeignDzLayout.IIIF3,
                )
            else:
                img.dzsave(
                    os.path.join(output_dir, isotope + ".dzi"),
                    id=id_url,
                    layout=pyvips.enums.ForeignDzLayout.IIIF3,
                )

            # Create or update MIMSOverlay record
            isotope_obj, _ = Isotope.objects.get_or_create(name=isotope)
            dzi_relative_path = os.path.join(relative_dir, isotope + ".dzi")

            overlay, created = MIMSOverlay.objects.get_or_create(
                image_set=image_set,
                isotope=isotope_obj,
                defaults={"mosaic": dzi_relative_path},
            )
            if not created:
                overlay.mosaic = dzi_relative_path
                overlay.save()

            print(f"Created overlay for {isotope}: {dzi_relative_path}")

        except Exception as e:
            print(f"Error processing isotope {isotope}: {e}")
            continue

    print(f"Completed creating overlays for image set {image_set.id}")


def create_isotope_composite(registered_images, isotope, canvas_width, canvas_height):
    """
    Create a canvas-sized composite image for a specific isotope by stitching together
    MimsTiffImages from all registered images using their registration bboxes.

    Rules:
      - No resizing. Paste-with-crop only.
      - No blending. New pixels overwrite existing ones ("last tile wins").
      - Cropping respects canvas bbox:
          * If x0 or y0 is negative, crop that many pixels from LEFT/TOP first.
          * Then clip any overflow on RIGHT/BOTTOM to the canvas.
      - Output is single-channel (grayscale), dtype taken from first pasted tile.
    """
    import numpy as np
    from PIL import Image

    # ----- Handle ratio composites by delegating -----
    if isotope == "13C12C_ratio":
        return create_ratio_composite(
            registered_images,
            ["12C", "12C2"],  # denominator candidates
            ["13C", "12C 13C"],  # numerator candidates
            canvas_width,
            canvas_height,
        )
    elif isotope == "15N14N_ratio":
        return create_ratio_composite(
            registered_images,
            ["14N 12C", "12C 14N"],  # denominator candidates
            ["15N 12C", "12C 15N"],  # numerator candidates
            canvas_width,
            canvas_height,
        )

    # Collect tiles for this isotope
    tiff_images = []
    for mims_image in registered_images:
        for tiff_image in mims_image.mims_tiff_images.filter(name=isotope):
            tiff_images.append((mims_image.id, tiff_image.id, tiff_image))

    if not mims_image.mims_tiff_images.filter(name=isotope):
        return None

    composite = None  # will be allocated on first successful paste

    pasted_any = False
    out_dtype = None

    for tiff_image in mims_image.mims_tiff_images.filter(name=isotope).order_by("name"):
        bbox = tiff_image.registration_bbox
        if not bbox:
            continue

        try:
            img = Image.open(tiff_image.image.path)
            src = np.array(img)
        except Exception as e:
            print(f"Error loading tiff image {tiff_image.id}: {e}")
            continue

        # Convert to grayscale plane (float32 if luma computed; otherwise original dtype)
        gray = src
        # Establish output buffer/dtype on first tile
        if composite is None:
            if np.issubdtype(gray.dtype, np.floating) or np.max(gray) > 255:
                out_dtype = np.uint16 if src.dtype == np.uint16 else np.uint8
            else:
                out_dtype = gray.dtype
            composite = np.zeros((canvas_height, canvas_width), dtype=out_dtype)

        # If gray is float (from luma), rescale to out_dtype range before paste
        if np.issubdtype(gray.dtype, np.floating):
            # Map 0..255 or 0..65535 depending on src depth heuristics
            # If original src was uint16, assume 0..65535 target, else 0..255
            if out_dtype == np.uint16:
                gray = np.clip(gray, 0, 65535).astype(np.uint16)
            else:
                gray = np.clip(gray, 0, 255).astype(np.uint8)

        Hs, Ws = gray.shape[:2]

        # ----- Raw bbox from registration (do NOT clamp yet) -----
        # bbox assumed as [ [x0,y0], [x1,y1], [x2,y2], [x3,y3] ]
        # where [0] is top-left and [2] is bottom-right
        try:
            x0_raw, y0_raw = int(bbox[0][0]), int(bbox[0][1])
            x1_raw, y1_raw = int(bbox[2][0]), int(bbox[2][1])
        except Exception:
            # Fallback: if bbox is dict or other format, try keys
            x0_raw = int(bbox.get("x0", 0))
            y0_raw = int(bbox.get("y0", 0))
            x1_raw = int(bbox.get("x1", 0))
            y1_raw = int(bbox.get("y1", 0))

        # Destination rect on canvas (clamped to canvas)
        dest_x0 = max(0, x0_raw)
        dest_y0 = max(0, y0_raw)
        dest_x1 = min(canvas_width, x1_raw)
        dest_y1 = min(canvas_height, y1_raw)

        if dest_x1 <= dest_x0 or dest_y1 <= dest_y0:
            # Entire bbox is outside canvas
            continue

        # Width/height of clamped destination rect
        dst_w = dest_x1 - dest_x0
        dst_h = dest_y1 - dest_y0

        # ----- Source crop offsets (crop LEFT/TOP first for negative corners) -----
        # If x0_raw < 0, we need to skip -x0_raw columns from source's LEFT edge.
        src_x0 = max(0, -x0_raw)
        src_y0 = max(0, -y0_raw)

        # Start with intended copy size equal to dest rect
        copy_w = dst_w
        copy_h = dst_h

        # But ensure we don't read past the source
        if src_x0 + copy_w > Ws:
            copy_w = Ws - src_x0
        if src_y0 + copy_h > Hs:
            copy_h = Hs - src_y0

        if copy_w <= 0 or copy_h <= 0:
            continue

        # Final paste (overwrite — no blending)
        composite[dest_y0 : dest_y0 + copy_h, dest_x0 : dest_x0 + copy_w] = gray[
            src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w
        ]

        pasted_any = True

    return composite if pasted_any else None


def create_ratio_composite(
    registered_images, denominator_names, numerator_names, canvas_width, canvas_height
):
    """
    Create a ratio composite (e.g., 13C/12C) by dividing two isotope composites.
    """
    # Get the denominator composite
    denom_isotope = None
    for name in denominator_names:
        denom_composite = create_isotope_composite(
            registered_images, name, canvas_width, canvas_height
        )
        if denom_composite is not None:
            denom_isotope = name
            break

    if denom_composite is None:
        return None

    # Get the numerator composite
    numer_composite = None
    for name in numerator_names:
        numer_composite = create_isotope_composite(
            registered_images, name, canvas_width, canvas_height
        )
        if numer_composite is not None:
            break

    if numer_composite is None:
        return None

    # Calculate ratio, avoiding division by zero
    denom_composite = denom_composite.astype(np.float32)
    numer_composite = numer_composite.astype(np.float32)

    # Set zeros to 1 to avoid division by zero
    denom_composite[denom_composite == 0] = 1

    # Calculate ratio and scale by 10000 (same as preprocessing)
    ratio = (numer_composite / denom_composite * 10000).astype(np.uint16)

    return ratio


def update_mims_image_set_status(image_set_id):
    """
    Update MIMSImageSet status based on the completion status of all MIMSImage objects in the set.

    Sets to:
    - PARTIALLY_REGISTERED: If some but not all images are complete
    - REGISTERED: If all images are REGISTERED, INVALID_FILE, or OUTSIDE_CANVAS

    When transitioning to REGISTERED, creates composite overlays in tmp_images location.
    """
    image_set = MIMSImageSet.objects.get(id=image_set_id)
    mims_images = image_set.mims_images.all()

    # Store previous status to detect transition
    previous_status = image_set.status

    # Define completed statuses
    completed_statuses = [
        MIMSImage.Status.REGISTERED,
        MIMSImage.Status.INVALID_FILE,
        MIMSImage.Status.OUTSIDE_CANVAS,
    ]

    # Count images by status
    total_images = mims_images.count()
    completed_images = mims_images.filter(status__in=completed_statuses).count()
    registered_images = mims_images.filter(status=MIMSImage.Status.REGISTERED).count()

    # Determine new status
    if completed_images == total_images:
        # All images are in a completed state
        new_status = MIMSImageSet.Status.REGISTERED
    elif registered_images > 0:
        # Some images are registered but not all are complete
        new_status = MIMSImageSet.Status.PARTIALLY_REGISTERED
    else:
        # No images are registered yet, keep current status
        return

    # Update if status changed
    if image_set.status != new_status:
        image_set.status = new_status
        image_set.save(update_fields=["status"])
        print(f"Updated MIMSImageSet {image_set_id} status to {new_status}")

        # If transitioning from PARTIALLY_REGISTERED to REGISTERED, create final overlays
        if (
            previous_status == MIMSImageSet.Status.PARTIALLY_REGISTERED
            and new_status == MIMSImageSet.Status.REGISTERED
        ):
            create_registered_overlays(image_set)

    return new_status
