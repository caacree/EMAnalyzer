// useOsdAnnotations.ts
import { useEffect, useState } from "react";
import OpenSeadragon from "openseadragon";
import { v4 as uuidv4 } from 'uuid';

// Import your store interface
import { CanvasStore as CanvasStoreType } from "@/interfaces/CanvasStore";
// Import your drawing utils
import addPointsAndOverlays from "@/utils/openseadragon/addPointsAndOverlays";
import drawEphemeralStrokeInViewport from "@/utils/openseadragon/drawEphemeralStrokeInViewport";


function getCursorSVG(brushSize: number, strokeWidth = 2, color = "black") {
  const radius = brushSize / 2;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${brushSize}" height="${brushSize}">
      <circle cx="${radius}" cy="${radius}" r="${radius - strokeWidth}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" />
    </svg>
  `;
  return `data:image/svg+xml;base64,${btoa(svg)}`;
}


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
  const [brushCursorCoordinates, setBrushCursorCoordinates] = useState<[number, number] | null>(null);

  const getImgPt = (e: OpenSeadragon.CanvasPressEvent | OpenSeadragon.CanvasDragEvent | OpenSeadragon.CanvasReleaseEvent | OpenSeadragon.CanvasClickEvent,
  ) => {
    const viewer = osdViewer;
    if (!viewer) return;
    // 1) Convert screen pixel -> "default" viewport coords (ignores flip/rotation)
    const vpPt = viewer.viewport.pointFromPixel(e.position);
    if (!vpPt) return null;
    // 7) Now we have the unflipped/unrotated viewport coords for that click
    const tiledImage = viewer.world.getItemAt(0);
    if (!tiledImage) return null;
    const testImgCoords = tiledImage.viewportToImageCoordinates(vpPt.x, vpPt.y);
    return testImgCoords;
  }

  useEffect(() => {
    // If user just switched away from "draw", clear out ephemeral data
    if (mode !== "draw") {
      setActiveStroke(null);
      setBrushCursorCoordinates(null);
    }
  }, [mode]);
  /**
   * 1) Attach OSD "canvas-press"/"canvas-drag"/"canvas-release" ONLY if we're in "draw" mode.
   *    This effect DOES NOT redraw ephemeral strokes; it only registers event handlers.
   */
  useEffect(() => {
    if (!osdViewer || mode !== "draw") return;
  
    // --- Handlers ---
    function handlePress(e: OpenSeadragon.CanvasPressEvent) {
      const imgPt = getImgPt(e);
      if (!imgPt) return;
      const strokeId = uuidv4();
      setActiveStroke({ id: strokeId, path: [[imgPt.x, imgPt.y, 0.5]] });
      // Hide the brush cursor circle while pressing
      setBrushCursorCoordinates(null);
    }
  
    function handleDrag(e: OpenSeadragon.CanvasDragEvent) {
      setActiveStroke(old => {
        if (!old || !osdViewer?.viewport) return null;
        const imgPt = getImgPt(e);
        if (!imgPt) return old;
        return {
          ...old,
          path: [...old.path, [imgPt.x, imgPt.y, 0.5]],
        };
      });
    }
  
    function handleRelease(e: OpenSeadragon.CanvasReleaseEvent) {
      if (!osdViewer?.viewport) return;
      const imgPt = getImgPt(e);
      if (!imgPt) return;

      setActiveStroke(old => {
        if (!old) return null;
        const strokeId = old.id;
        const { path: imgPath } = old;
        
        // Finalize the stroke in your store
        addOverlay({
          id: strokeId,
          data: { polygon: [...imgPath, [imgPt.x, imgPt.y, 0.5]] },
          color: "red",
          type: "brush_stroke",
          fill: true,
          visible: true,
        });
        
        drawEphemeralStrokeInViewport(osdViewer, brushSize, []);
        return null;
      });
    }
  
    // --- Attach them ---
    osdViewer.addHandler("canvas-press", handlePress);
    osdViewer.addHandler("canvas-drag", handleDrag);
    osdViewer.addHandler("canvas-release", handleRelease);
  
    // --- Cleanup ---
    return () => {
      osdViewer.removeHandler("canvas-press", handlePress);
      osdViewer.removeHandler("canvas-drag", handleDrag);
      osdViewer.removeHandler("canvas-release", handleRelease);
    };
    // Notice that we're NOT including `activeStroke` in the dependency array here.
    // If we did, we'd re-attach the handlers whenever the stroke changes.
  }, [osdViewer, mode, brushSize]);

  // Each time the viewer changes or the “mode” changes, re-attach event handlers.
  useEffect(() => {
    if (!osdViewer?.element) return;
    // Clear relevant handlers
    osdViewer.removeAllHandlers("canvas-click");

    if (mode === "shapes" || mode === "points") {
      osdViewer.addHandler("canvas-click", e => {
        const imgPt = getImgPt(e);
        if (!imgPt) return;

        addPoint({
          id: uuidv4(),
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

  /**
   * 3) Draw ephemeral stroke & cursor each render (when in "draw" mode).
   *    This effect re-runs whenever any relevant state changes,
   *    but does NOT re-attach event handlers.
   */
  useEffect(() => {
    if (!osdViewer?.element) return;
    if (mode === "draw" || mode === "shapes") {
      const cursorUrl = getCursorSVG(brushSize, 2, "red");
      osdViewer.element.style.cursor = `url(${cursorUrl}) ${brushSize / 2} ${brushSize / 2}, auto`;
      // Re-draw the ephemeral brush stroke in the viewport
      if (activeStroke?.path) {
        drawEphemeralStrokeInViewport(
          osdViewer,
          brushSize,
          activeStroke?.path,
        );
      }
    } else {
      // Reset to default cursor when not drawing
      osdViewer.element.style.cursor = "auto";
    }
  }, [
    osdViewer,
    mode,
    activeStroke,
    brushCursorCoordinates,
    flip,
    rotation,
    brushSize,
  ]);

  // Whenever points, overlays, or flip/rotation change, re-draw everything
  useEffect(() => {
    if (!osdViewer) return;
    addPointsAndOverlays(osdViewer, points, overlays, flip, rotation);
  }, [osdViewer, points, overlays, flip, rotation]);
}
