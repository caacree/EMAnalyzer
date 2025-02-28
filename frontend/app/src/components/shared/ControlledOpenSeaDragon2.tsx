import React from "react";
import { CanvasStore as CanvasStoreType } from "@/interfaces/CanvasStore";
import {
  OpenSeadragonAnnotator,
  OpenSeadragonViewer
} from '@annotorious/react';


interface ControlledOpenSeaDragonProps {
  iiifContent?: string;
  url?: string;
  canvasStore: CanvasStoreType;
  mode: "shapes" | "draw" | "navigate" | "points";
  pointSelectionMode?: "include" | "exclude";
  brushSize?: number; // in "pixel-like" units
}

const ControlledOpenSeaDragon: React.FC<ControlledOpenSeaDragonProps> = ({
  iiifContent,
  url,
  canvasStore,
  mode = "navigate",
  pointSelectionMode = "include",
  brushSize = 10
}) => {
  let allowZoom = false, allowFlip = false, allowRotation = false
  if (mode === "navigate") {
    allowZoom = true;
    allowFlip = true;
    allowRotation = true;
  }

  return (
      <OpenSeadragonAnnotator>
        <OpenSeadragonViewer options={{
          prefixUrl: "/openseadragon/images/",
          tileSources: [
            iiifContent
              ? { tileSource: iiifContent }
              : {
                  type: "image",
                  url,
                  buildPyramid: false
                }
          ],
          gestureSettingsMouse: {
            clickToZoom: allowZoom,
            scrollToZoom: allowZoom,
            pinchToZoom: allowZoom,
            dragToPan: mode === "navigate"
          },
          gestureSettingsTouch: {
            pinchToZoom: allowZoom, 
            dragToPan: mode === "navigate"
          },
          zoomPerClick: allowZoom ? 2 : 1,
          zoomPerScroll: allowZoom ? 1.2 : 1,
          showNavigator: mode === "navigate",
          panHorizontal: mode === "navigate",
          panVertical: mode === "navigate",
          showNavigationControl: mode === "navigate",
          showZoomControl: mode === "navigate",
          showRotationControl: false,
          crossOriginPolicy: "Anonymous"
        }} />
      </OpenSeadragonAnnotator>
  );
};

export default ControlledOpenSeaDragon;
