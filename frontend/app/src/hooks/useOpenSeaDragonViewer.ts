// useOpenSeadragonViewer.ts
import { useRef, useEffect } from "react";
import OpenSeadragon from "openseadragon";
import { CanvasStore as CanvasStoreType } from "@/interfaces/CanvasStore";
interface UseOpenSeadragonViewerProps {
  iiifContent?: string;
  url?: string;
  canvasStore: CanvasStoreType;
  mode: "shapes" | "draw" | "navigate" | "points";
}

export function useOpenSeadragonViewer({
  iiifContent,
  url,
  mode = "navigate",
  canvasStore
}: UseOpenSeadragonViewerProps) {
  // HTML container for OSD
  const viewerRef = useRef<HTMLDivElement | null>(null);
  // Store the OSD viewer instance
  const osdViewerRef = useRef<OpenSeadragon.Viewer | null>(null);

  const {
    zoom,
    flip,
    rotation,
    coordinates,
    setFlip,
    setRotation,
    setZoom
  } = canvasStore;

  let allowZoom = false, allowFlip = false, allowRotation = false
  if (mode === "navigate") {
    allowZoom = true;
    allowFlip = true;
    allowRotation = true;
  }

  // Create or re-create the viewer
  useEffect(() => {
    if (!viewerRef.current || (!iiifContent && !url)) return;

    // Destroy any existing
    if (osdViewerRef.current) {
      osdViewerRef.current.destroy();
    }
    osdViewerRef.current = OpenSeadragon({
      prefixUrl: "/openseadragon/images/",
      element: viewerRef.current,
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
    });
    
    const viewer = osdViewerRef.current;
    viewer.addHandler('canvas-key',event => {
      if (['q', 'w', 'e', 'r', 'a', 's', 'd', 'f'].includes(event.originalEvent.key)) {
          event.preventDefaultAction = true;
      }
    });

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
    if (allowZoom) {
      viewer.addHandler("zoom", () => {
        const vp = viewer.viewport;
        if (!vp) return;
        const newZoom = vp.viewportToImageZoom(vp.getZoom());
        if (newZoom !== zoom) {
          setZoom(newZoom);
        }
      });
    }
    // Fit to initial coordinates if provided
    if ((coordinates && coordinates.length > 0) || flip || rotation) {
      viewer.addOnceHandler("open", () => {
        const tiledImage = viewer.world.getItemAt(0);
        if (!tiledImage) return;
        if (coordinates && coordinates.length > 1) {
          const tl = {x: coordinates[0].x, y: coordinates[0].y};
          const br = {x: coordinates[1].x, y: coordinates[1].y};
          if (flip) {
            tl.x = tiledImage.getContentSize().x - tl.x;
            br.x = tiledImage.getContentSize().x - br.x;
          }
          const topLeft = tiledImage.imageToViewportCoordinates(
            tl.x,
            tl.y
          );
          const bottomRight = coordinates[1]
            ? tiledImage.imageToViewportCoordinates(
                br.x,
                br.y
              )
            : tiledImage.imageToViewportCoordinates(
                br.x,
                br.y
              );

          const bounds = new OpenSeadragon.Rect(
            topLeft.x,
            topLeft.y,
            bottomRight.x - topLeft.x,
            bottomRight.y - topLeft.y
          );
          viewer.viewport.fitBounds(bounds, true);
        }
        if (rotation) {
          tiledImage.setRotation(-rotation);
          viewer.viewport.goHome(true);
        }
        if (flip) {
          tiledImage.setFlip(flip);
        }
      });
    }

    // Clean up on unmount
    return () => {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }
    };
  }, [iiifContent, url, viewerRef.current]);

  useEffect(() => {
    const viewer = osdViewerRef.current as any;
    if (!viewer) return;
    viewer.forceRedraw();
  }, [coordinates]);

  useEffect(() => {
    const viewer = osdViewerRef.current as any;
    if (!viewer) return;
    viewer.gestureSettingsMouse = {
      clickToZoom: mode === "navigate",
      scrollToZoom: mode === "navigate",
      pinchToZoom: mode === "navigate",
      dragToPan: mode === "navigate"
    }
    viewer.gestureSettingsTouch = {
      pinchToZoom: mode === "navigate",
      dragToPan: mode === "navigate"
    }
    viewer.zoomPerClick = mode === "navigate" ? 2 : 1;
    viewer.zoomPerScroll = mode === "navigate" ? 1.2 : 1;
    viewer.panHorizontal = mode === "navigate";
    viewer.panVertical = mode === "navigate";
    viewer.showNavigator = mode === "navigate";
    viewer.showNavigationControl = mode === "navigate";
    viewer.showZoomControl = mode === "navigate";
    viewer.showRotationControl = mode === "navigate";
    viewer.forceRedraw();
  }, [mode])

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
    const tiledImage = viewer.world.getItemAt(0);
    if (!tiledImage) return;

    const currentRotation = tiledImage.getRotation();
    if (currentRotation !== rotation) {
      tiledImage.setRotation(-rotation);
    }
  }, [rotation]);

  // Keep OSD flip in sync
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer || !viewer.viewport) return;
    const tiledImage = viewer.world.getItemAt(0);
    if (!tiledImage) return;
    const currentFlip = tiledImage.getFlip();
    if (currentFlip !== flip) {
      tiledImage.setFlip(flip);
    }
  }, [flip]);

  // Return the DOM ref (for the <div>) and the OSD instance
  return {
    viewerRef,
    osdViewer: osdViewerRef.current
  };
}
