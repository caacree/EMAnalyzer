// useOsdAnnotations.ts
import { useEffect, useState } from "react";
import OpenSeadragon from "openseadragon";

// Import your store interface
import { CanvasStore as CanvasStoreType } from "@/interfaces/CanvasStore";
// Import your drawing utils
import addPointsAndOverlays from "@/utils/openseadragon/addPointsAndOverlays";
import drawEphemeralStrokeInViewport from "@/utils/openseadragon/drawEphemeralStrokeInViewport";

interface UseOsdAnnotationsProps {
  osdViewer: OpenSeadragon.Viewer | null;
  canvasStore: CanvasStoreType;
  mode: "shapes" | "draw" | "navigate";
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
  let allowZoom = false, allowBrush = false, allowPointSelection = false;
  if (mode === "shapes") {
    allowPointSelection = true;
  } else if (mode === "draw") {
    allowBrush = true;
  } else if (mode === "navigate") {
    allowZoom = true;
  }
  const {
    zoom,
    flip,
    rotation,
    points,
    overlays,
    setZoom,
    addPoint,
    addOverlay
    // ... other store fields if needed
  } = canvasStore;

  // Local state for ephemeral brush strokes
  const [activeStroke, setActiveStroke] = useState<{
    id: string;
    path: [number, number][];
    strokeWidth: number;
  } | null>(null);

  // Each time the viewer changes or the “mode” changes, re-attach event handlers.
  useEffect(() => {
    if (!osdViewer) return;

    // Clear relevant handlers
    osdViewer.removeAllHandlers("zoom");
    osdViewer.removeAllHandlers("canvas-click");
    osdViewer.removeAllHandlers("canvas-press");
    osdViewer.removeAllHandlers("canvas-drag");
    osdViewer.removeAllHandlers("canvas-release");
    osdViewer.removeAllHandlers("pan");

    // (1) Zoom handler
    if (allowZoom) {
      osdViewer.addHandler("zoom", () => {
        const vp = osdViewer.viewport;
        if (!vp) return;
        const newZoom = vp.viewportToImageZoom(vp.getZoom());
        if (newZoom !== zoom) {
          setZoom(newZoom);
        }
      });
    }

    // (2) Pan handler (if you want to track bounds)
    osdViewer.addHandler("pan", () => {
      // For now we only handle if you want to do something in store
      // e.g. setCoordinates(...) with bounding box
    });

    // (3) Point-click selection
    if (allowPointSelection) {
      osdViewer.addHandler("canvas-click", e => {
        const vp = osdViewer.viewport;
        if (!vp) return;
        const tiledImage = osdViewer.world.getItemAt(0);
        if (!tiledImage) return;

        const imageCoords = tiledImage.viewerElementToImageCoordinates(e.position);

        addPoint({
          id: Math.random().toString(),
          x: imageCoords.x,
          y: imageCoords.y,
          type: pointSelectionMode,
          color: pointSelectionMode === "include" ? "green" : "red"
        });
      });

      // Prevent default keyboard drag
      osdViewer.addHandler("canvas-key", (e: any) => {
        e.preventDefaultAction = true;
      });
    }

    // (4) Brush mode
  }, [
    osdViewer,
    allowZoom,
    allowPointSelection,
    allowBrush,
    brushSize
  ]);

  // Handle ephemeral stroke rendering (on every render).
  useEffect(() => {
    if (!osdViewer) return;
    if (activeStroke && activeStroke.path.length > 1) {
      drawEphemeralStrokeInViewport(
        osdViewer,
        activeStroke.path,
        activeStroke.strokeWidth
      );
    }
    if (allowBrush) {
      // Press
      osdViewer.addHandler("canvas-press", e => {
        if (!osdViewer.viewport) return;
        const vpPt = osdViewer.viewport.pointFromPixel(e.position, true);
        const strokeId = Math.random().toString();

        setActiveStroke({
          id: strokeId,
          path: [[vpPt.x, vpPt.y]],
          strokeWidth: brushSize
        });
      });

      // Drag
      osdViewer.addHandler("canvas-drag", e => {
        setActiveStroke(old => {
          if (!old || !osdViewer.viewport) return null;
          const vpPt = osdViewer.viewport.pointFromPixel(e.position, true);
          return {
            ...old,
            path: [...old.path, [vpPt.x, vpPt.y]]
          };
        });
      });

      // Release
      osdViewer.addHandler("canvas-release", () => {
        if (!activeStroke || !osdViewer.viewport) return;
        const strokeId = activeStroke.id;
        const { path: vpPath, strokeWidth } = activeStroke;

        const tiledImage = osdViewer.world.getItemAt(0);
        if (!tiledImage) return;

        // Convert from viewport coords to image coords
        const pathInImageCoords = vpPath.map(([vx, vy]) => {
          const { x, y } = tiledImage.viewportToImageCoordinates(vx, vy);
          return [x, y];
        });

        // Add the overlay
        addOverlay({
          id: strokeId,
          data: { path: pathInImageCoords },
          color: "red",
          type: "brush_stroke",
          strokeWidth
        });

        setActiveStroke(null);
      });
    }
    if (activeStroke) {
      drawEphemeralStrokeInViewport(osdViewer, activeStroke.path, activeStroke.strokeWidth);
    }
  }, [osdViewer, activeStroke]);

  // Whenever points, overlays, or flip/rotation change, re-draw everything
  useEffect(() => {
    if (!osdViewer) return;
    addPointsAndOverlays(osdViewer, points, overlays, flip, rotation);
  }, [osdViewer, points, overlays, flip, rotation]);
}
