import React from "react";
import { useOpenSeadragonViewer } from "@/hooks/useOpenSeaDragonViewer";
import { useOsdAnnotations } from "@/hooks/useOsdAnnotations";

interface ControlledOpenSeaDragonProps {
  iiifContent?: string;
  url?: string;
  positionedImages?: Array<{
    url: string;
    name: string;
    bounds: number[] | null;
  }>;
  canvasStore: any;
  mode?: "shapes" | "draw" | "navigate" | "points";
  pointSelectionMode?: "include" | "exclude";
  brushSize?: number; // in "pixel-like" units
}

const ControlledOpenSeaDragon: React.FC<ControlledOpenSeaDragonProps> = ({
  iiifContent,
  url,
  positionedImages,
  canvasStore,
  mode = "shapes",
  pointSelectionMode = "include",
  brushSize = 10
}) => {
  // 1) Create the OSD viewer and sync basic transforms (zoom/flip/rotation)
  //    in the useOpenSeadragonViewer hook.
  const { viewerRef, osdViewer, isContainerReady, isViewerInitialized } = useOpenSeadragonViewer({
    iiifContent,
    url,
    positionedImages,
    mode,
    canvasStore
  });

  // 2) Attach annotation logic (points, overlays, brush strokes, ephemeral stroke)
  //    in a separate hook.
  useOsdAnnotations({
    osdViewer,
    storeApi: canvasStore,
    mode,
    pointSelectionMode,
    brushSize
  });

  return (
    <div
      ref={viewerRef}
      className="flex grow border h-full min-h-[400px] relative"
      id={`controlled-openseadragon-${iiifContent || url}`}
    >
      {(!isContainerReady|| !isViewerInitialized) && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 bg-opacity-75 z-10">
          <div className="flex flex-col items-center gap-2">
            <div className="animate-spin h-6 w-6 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            <span className="text-gray-600 text-sm">
              {!isContainerReady && "Waiting for container..."}
              {isContainerReady && !isViewerInitialized && "Initializing viewer..."}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ControlledOpenSeaDragon;
