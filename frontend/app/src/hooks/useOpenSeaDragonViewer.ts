// useOpenSeadragonViewer.ts
import { useRef, useEffect } from "react";
import OpenSeadragon from "openseadragon";
import { CanvasStore as CanvasStoreType } from "@/interfaces/CanvasStore";
interface UseOpenSeadragonViewerProps {
  iiifContent?: string;
  url?: string;
  canvasStore: CanvasStoreType;
  mode: "shapes" | "draw" | "navigate";
}

export function useOpenSeadragonViewer({
  iiifContent,
  url,
  mode = "navigate",
  canvasStore
}: UseOpenSeadragonViewerProps) {
  // HTML container for OSD
  const viewerRef = useRef<HTMLDivElement | null>(null);

  const {
    zoom,
    flip,
    rotation,
    coordinates,
    setFlip,
    setRotation
  } = canvasStore;

  let allowZoom = false, allowFlip = false, allowRotation = false, allowPan = false;
  if (mode === "navigate") {
    allowZoom = true;
    allowFlip = true;
    allowRotation = true;
    allowPan = true;
  }

  // Store the OSD viewer instance
  const osdViewerRef = useRef<OpenSeadragon.Viewer | null>(null);

  // Create or re-create the viewer
  useEffect(() => {
    if (!viewerRef.current || (!iiifContent && !url)) return;

    // Destroy any existing
    if (osdViewerRef.current) {
      osdViewerRef.current.destroy();
    }

    osdViewerRef.current = OpenSeadragon({
      prefixUrl: "/openseadragon/images/",
      id: viewerRef.current.id,
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
        pinchToZoom: allowZoom
      },
      gestureSettingsTouch: {
        pinchToZoom: allowZoom
      },
      zoomPerClick: allowZoom ? 2 : 1,
      zoomPerScroll: allowZoom ? 1.2 : 1,
      zoomPerDblClickDrag: allowZoom ? 1.2 : 1,
      showNavigator: allowZoom || allowRotation,
      panHorizontal: allowPan,
      panVertical: allowPan,
      showNavigationControl: allowZoom || allowRotation,
      showZoomControl: allowZoom,
      showRotationControl: allowRotation,
      crossOriginPolicy: "Anonymous"
    });

    const viewer = osdViewerRef.current;

    // If we allow rotation, wire up the OSD rotate event
    if (allowRotation) {
      viewer.addHandler("rotate", () => {
        const newRotation = viewer.viewport.getRotation();
        if (newRotation !== rotation) {
          setRotation(newRotation);
        }
      });
    }

    // If we allow flip, wire up the OSD flip event
    if (allowFlip) {
      viewer.addHandler("flip", () => {
        const newFlip = viewer.viewport.getFlip();
        if (newFlip !== flip) {
          setFlip(newFlip);
        }
      });
    }

    // Fit to initial coordinates if provided
    if (coordinates && coordinates.length > 0) {
      viewer.addOnceHandler("open", () => {
        const tiledImage = viewer.world.getItemAt(0);
        if (!tiledImage) return;

        const topLeft = tiledImage.imageToViewportCoordinates(
          coordinates[0].x,
          coordinates[0].y
        );
        const bottomRight = coordinates[1]
          ? tiledImage.imageToViewportCoordinates(
              coordinates[1].x,
              coordinates[1].y
            )
          : tiledImage.imageToViewportCoordinates(
              coordinates[0].x + 1,
              coordinates[0].y + 1
            );

        const bounds = new OpenSeadragon.Rect(
          topLeft.x,
          topLeft.y,
          bottomRight.x - topLeft.x,
          bottomRight.y - topLeft.y
        );
        viewer.viewport.fitBounds(bounds, true);
      });
    }

    // Clean up on unmount
    return () => {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [iiifContent, url]);

  // Keep OSD zoom in sync with store
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer || !viewer.viewport) return;

    const currentZoom = viewer.viewport.viewportToImageZoom(viewer.viewport.getZoom());
    if (currentZoom !== zoom) {
      viewer.viewport.zoomTo(viewer.viewport.imageToViewportZoom(zoom), undefined, true);
    }
  }, [zoom]);

  // Keep OSD rotation in sync
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer || !viewer.viewport) return;

    const currentRotation = viewer.viewport.getRotation();
    if (currentRotation !== rotation) {
      viewer.viewport.setRotation(rotation);
    }
  }, [rotation]);

  // Keep OSD flip in sync
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer || !viewer.viewport) return;

    const currentFlip = viewer.viewport.getFlip();
    if (currentFlip !== flip) {
      viewer.viewport.setFlip(flip);
    }
  }, [flip]);

  // Return the DOM ref (for the <div>) and the OSD instance
  return {
    viewerRef,
    osdViewer: osdViewerRef.current
  };
}
