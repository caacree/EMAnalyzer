
import { CanvasOverlay as CanvasOverlayType } from "@/interfaces/CanvasOverlay";
import { Point as PointType } from "@/interfaces/Point";
import { drawBrushStrokeOverlay } from "./drawBrushStrokes";
import { drawPolygonOrBboxOverlay } from "./drawPolygonOrBboxOverlay";
import newPointIndicator from "../newPointIndicator";
import OpenSeadragon from "openseadragon";

export default function addPointsAndOverlays(
  viewer: OpenSeadragon.Viewer,
  pointsData: PointType[],
  overlaysData: CanvasOverlayType[],
  flip: boolean,
  rotation: number
) {
  try {
    viewer.clearOverlays();
  } catch (error) {
    // pass
  }

  // 1) Draw polygons/bboxes/brush fill
  overlaysData.forEach(overlay => {
    if (overlay.type === "brush_stroke") {
      // Render the freehand stroke as a polyline
      drawBrushStrokeOverlay(viewer, overlay, flip, rotation);
    } else {
      // Polygons, bounding boxes, suggestions, confirmed shapes, etc.
      drawPolygonOrBboxOverlay(viewer, overlay, flip, rotation);
    }
  });

  // 2) Draw single points (include/exclude clicks)
  pointsData.forEach((point, idx) => {
    viewer.addOverlay({
      id: point.id,
      element: newPointIndicator(idx + 1, point.color || "red", true),
      px: point.x,
      py: point.y,
      placement: OpenSeadragon.Placement.CENTER,
      checkResize: false,
      rotationMode: OpenSeadragon.OverlayRotationMode.EXACT
    });
  });
  // 3) Render ephemeral stroke if it exists in viewport coords
  
}