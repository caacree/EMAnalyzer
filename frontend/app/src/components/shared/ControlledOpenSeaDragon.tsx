import React from "react";
import { CanvasStore as CanvasStoreType } from "@/interfaces/CanvasStore";
import { useOpenSeadragonViewer } from "@/hooks/useOpenSeaDragonViewer";
import { useOsdAnnotations } from "@/hooks/useOsdAnnotations";

interface ControlledOpenSeaDragonProps {
  iiifContent?: string;
  url?: string;
  canvasStore: CanvasStoreType;
  mode?: "shapes" | "draw" | "navigate" | "points";
  pointSelectionMode?: "include" | "exclude";
  brushSize?: number; // in "pixel-like" units
}

const ControlledOpenSeaDragon: React.FC<ControlledOpenSeaDragonProps> = ({
  iiifContent,
  url,
  canvasStore,
  mode = "shapes",
  pointSelectionMode = "include",
  brushSize = 10
}) => {

  // 1) Create the OSD viewer and sync basic transforms (zoom/flip/rotation)
  //    in the useOpenSeadragonViewer hook.
  const { viewerRef, osdViewer } = useOpenSeadragonViewer({
    iiifContent,
    url,
    mode,
    canvasStore
  });

  // 2) Attach annotation logic (points, overlays, brush strokes, ephemeral stroke)
  //    in a separate hook.
  useOsdAnnotations({
    osdViewer,
    canvasStore,
    mode,
    pointSelectionMode,
    brushSize
  });

  return (
    <div
      ref={viewerRef}
      className="flex grow border h-full"
      id={`controlled-openseadragon-${iiifContent || url}`}
    />
  );
};

export default ControlledOpenSeaDragon;
