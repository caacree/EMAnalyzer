import { CanvasOverlay as CanvasOverlayType } from "@/interfaces/CanvasOverlay";
import { Point as PointType } from "@/interfaces/Point";
import { drawPolygonOrBboxOverlay } from "./drawPolygonOrBboxOverlay";
import newPointIndicator from "../newPointIndicator";
import OpenSeadragon from "openseadragon";

export default function addPointsAndOverlays(
  viewer: OpenSeadragon.Viewer,
  pointsData: PointType[],
  overlaysData: CanvasOverlayType[],
) {
  try {
    viewer.clearOverlays();
  } catch (error) {
    // pass
  }

  // 1) Draw polygons/bboxes/brush fill
  if (overlaysData && Array.isArray(overlaysData)) {
    overlaysData.forEach(overlay => {
        // Polygons, bounding boxes, suggestions, confirmed shapes, etc.
        drawPolygonOrBboxOverlay(viewer, overlay);
    });
  }

  // 2) Draw single points (include/exclude clicks)
  if (pointsData && Array.isArray(pointsData)) {
    pointsData.forEach((point, idx) => {
      const tiledImage = viewer.world.getItemAt(0);
      if (!tiledImage) return;
      const flip = tiledImage.getFlip();
      const contentSize = tiledImage.getContentSize();
      const px = flip ? contentSize.x - point.x : point.x;
      const py = point.y;
      viewer.addOverlay({
        id: point.id,
        element: newPointIndicator(idx + 1, point.color || "red", true),
        px: px,
        py: py,
        placement: OpenSeadragon.Placement.CENTER,
        checkResize: false,
        rotationMode: OpenSeadragon.OverlayRotationMode.EXACT
      });
    });
  }
}