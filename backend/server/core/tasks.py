from celery import shared_task
from process_canvas_registration import process_canvas_registration


@shared_task
def prep_canvas(canvas_id):
    """
    Prepare a canvas for viewing by ensuring all required DZI files exist.

    This task wraps process_canvas_registration which will:
    1. Create EM image DZI files if missing
    2. Process MIMS image sets (extract isotopes, create composites)
    3. Register MIMS images if needed
    4. Create overlay DZI files

    Args:
        canvas_id (str): Canvas UUID

    Returns:
        dict: Status report from process_canvas_registration
    """
    print(f"Starting prep_canvas task for canvas {canvas_id}")

    try:
        status = process_canvas_registration(canvas_id, force_reprocess=False)
        print(f"prep_canvas task completed for canvas {canvas_id}")
        return status
    except Exception as e:
        print(f"prep_canvas task failed for canvas {canvas_id}: {str(e)}")
        raise e
