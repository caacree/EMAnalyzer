// useOsdAnnotations.ts
import { useEffect, useState } from "react";
import OpenSeadragon from "openseadragon";

// Import your store interface
import { CanvasStore as CanvasStoreType } from "@/interfaces/CanvasStore";
// Import your drawing utils
import addPointsAndOverlays from "@/utils/openseadragon/addPointsAndOverlays";
import drawEphemeralStrokeInViewport from "@/utils/openseadragon/drawEphemeralStrokeInViewport";
import drawEphemeralBrushCursor from "@/utils/openseadragon/drawEphemeralBrushCursor";
import { strokePathToPolygon } from "@/utils/strokeToPolygon";

interface UseOsdAnnotationsProps {
  osdViewer: OpenSeadragon.Viewer | null;
  canvasStore: CanvasStoreType;
  mode: "shapes" | "draw" | "navigate" | "points";
  pointSelectionMode?: "include" | "exclude";
  brushSize?: number;
}

export function useOsdAnnotations({
  osdViewer,
  canvasStore,
  mode,
  pointSelectionMode = "include",
  brushSize = 10
}: UseOsdAnnotationsProps) {
  const {
    flip,
    rotation,
    points,
    overlays,
    addPoint,
    addOverlay
  } = canvasStore;

  // Local state for ephemeral brush strokes
  const [activeStroke, setActiveStroke] = useState<{
    id: string;
    path: [number, number, number][];
  } | null>(null);
  // Local state for showing the brush cursor circle
  const [brushCursor, setBrushCursor] = useState<[number, number] | null>(null);

  const getImgPt = (e: OpenSeadragon.CanvasPressEvent | OpenSeadragon.CanvasDragEvent | OpenSeadragon.CanvasReleaseEvent | OpenSeadragon.CanvasClickEvent) => {
    if (!osdViewer) return;
    const vpPt = osdViewer.viewport?.pointFromPixel(e.position, true);
    const tiledImage = osdViewer?.world.getItemAt(0);
    if (!tiledImage) return;
    return tiledImage.viewportToImageCoordinates(vpPt.x, vpPt.y);
  }

  // Each time the viewer changes or the “mode” changes, re-attach event handlers.
  useEffect(() => {
    if (!osdViewer) return;

    // Clear relevant handlers
    osdViewer.removeAllHandlers("canvas-click");

    if (mode === "shapes" || mode === "points") {
      osdViewer.addHandler("canvas-click", e => {
        const imgPt = getImgPt(e);
        if (!imgPt) return;

        addPoint({
          id: Math.random().toString(),
          x: imgPt.x,
          y: imgPt.y,
          type: pointSelectionMode,
          color: pointSelectionMode === "include" ? "green" : "red"
        });
      });
      // Prevent default keyboard drag
      osdViewer.addHandler("canvas-key", (e: any) => {
        e.preventDefaultAction = true;
      });
    }
  }, [
    osdViewer,
    mode,
    pointSelectionMode
  ]);

  // Handle ephemeral stroke rendering (on every render).
  useEffect(() => {
    if (!osdViewer) return;
    osdViewer.removeAllHandlers("canvas-press");
    osdViewer.removeAllHandlers("canvas-drag");
    osdViewer.removeAllHandlers("canvas-release");

    if (mode !== "draw") {
      setBrushCursor(null);
      setActiveStroke(null);
    }

    if (mode === "draw") {
      drawEphemeralStrokeInViewport(
        osdViewer,
        brushSize,
        flip,
        rotation,
        activeStroke?.path,
      );
      drawEphemeralBrushCursor(
        osdViewer,
        brushCursor,
        brushSize,
        flip,
        rotation
      );
      
      // Press
      osdViewer.addHandler("canvas-press", e => {
        const imgPt = getImgPt(e);
        if (!imgPt) return;
        const strokeId = Math.random().toString();
        setActiveStroke({
          id: strokeId,
          path: [[imgPt.x, imgPt.y, 0.5]],
        });
        if (brushCursor) {
          setBrushCursor(null);
        }
      });

      // Drag
      osdViewer.addHandler("canvas-drag", e => {
        setActiveStroke(old => {
          if (!old || !osdViewer.viewport) return null;
          const imgPt = getImgPt(e);
          if (!imgPt) return null;
          return {
            ...old,
            path: [...old.path, [imgPt.x, imgPt.y, 0.5]]
          };
        });
      });

      // Release
      osdViewer.addHandler("canvas-release", () => {
        if (!activeStroke || !osdViewer.viewport) return;
        const strokeId = activeStroke.id;
        const { path: imgPath } = activeStroke;

        // Add the overlay
        addOverlay({
          id: strokeId,
          data: { polygon: strokePathToPolygon(imgPath, brushSize) },
          color: "red",
          type: "brush_stroke",
          fill: true,
          visible: true,
        });

        setActiveStroke(null);
      });

      const container = osdViewer.element; 
      const onMouseMove = (ev: MouseEvent) => {
        // Only track if not actively drawing
        if (!activeStroke) {
          // Convert screen coords to container-relative coords
          const rect = container.getBoundingClientRect();
          const offsetX = ev.clientX - rect.left;
          const offsetY = ev.clientY - rect.top;
          
          // Convert to OSD viewport coords
          const vp = osdViewer?.viewport?.pointFromPixel(
            new OpenSeadragon.Point(offsetX, offsetY),
            true
          );
          if (vp) {
            setBrushCursor([vp.x, vp.y]);
          }
        }
      }
      
      const onMouseLeave = () => {
        setBrushCursor(null);
      }
      container.addEventListener("mousemove", onMouseMove);
      container.addEventListener("mouseleave", onMouseLeave);

      // Cleanup on unmount or when mode changes
      return () => {
        container.removeEventListener("mousemove", onMouseMove);
        container.removeEventListener("mouseleave", onMouseLeave);
      };
    }
  }, [osdViewer, mode, activeStroke, brushCursor]);

  // Whenever points, overlays, or flip/rotation change, re-draw everything
  useEffect(() => {
    if (!osdViewer) return;
    addPointsAndOverlays(osdViewer, points, overlays, flip, rotation);
  }, [osdViewer, points, overlays, flip, rotation]);
}
