import React, { useEffect, useRef } from "react";
import OpenSeadragon from 'openseadragon';

interface Overlay {
  element: HTMLElement;
  x: number;
  y: number;
}

interface ControlledOpenSeaDragonProps {
  iiifContent: string;
  zoom: number;
  flip: boolean;
  rotation: number;
  overlays: Overlay[];
  allowZoom?: boolean;
  allowFlip?: boolean;
  allowRotation?: boolean;
  allowSelection?: boolean;
  onZoomChange?: (zoom: number) => void;
  onFlipChange?: (flipped: boolean) => void;
  onRotationChange?: (rotation: number) => void;
}

const ControlledOpenSeaDragon: React.FC<ControlledOpenSeaDragonProps> = ({
  iiifContent,
  zoom,
  flip,
  rotation,
  overlays,
  allowZoom = false,
  allowFlip = false,
  allowRotation = false,
  allowSelection = false,
  onZoomChange,
  onFlipChange,
  onRotationChange,
}) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const osdViewerRef = useRef<OpenSeadragon.Viewer | null>(null);

  useEffect(() => {
    if (!viewerRef.current || !iiifContent) return;

    if (osdViewerRef.current) {
      osdViewerRef.current.destroy();
    }

    const osdOverlays = overlays.map((overlay) => ({
      element: overlay.element,
      location: new OpenSeadragon.Point(overlay.x, overlay.y),
      placement: OpenSeadragon.Placement.CENTER,
      checkResize: false,
      rotationMode: OpenSeadragon.OverlayRotationMode.NO_ROTATION,
    }));

    osdViewerRef.current = OpenSeadragon({
      prefixUrl: '/openseadragon/images/',
      id: viewerRef.current.id,
      tileSources: [{ tileSource: iiifContent }],
      minZoomLevel: 0.9,
      gestureSettingsMouse: {
        clickToZoom: allowZoom,
      },
      showNavigator: true,
      overlays: osdOverlays,
    });

    const viewer = osdViewerRef.current;

    viewer.addHandler('open', () => {
      const viewport = viewer.viewport;
      if (!viewport) return;

      // Set initial zoom
      const imageZoom = viewport.imageToViewportZoom(zoom);
      viewport.zoomTo(imageZoom, undefined, true);

      // Set initial rotation
      viewport.setRotation(rotation);

      // Set initial flip
      viewport.setFlip(flip);
    });

    if (allowZoom) {
      viewer.addHandler('zoom', () => {
        const viewport = viewer.viewport;
        if (!viewport || !onZoomChange) return;
        const newZoom = viewport.viewportToImageZoom(viewport.getZoom());
        onZoomChange(newZoom);
      });
    }

    if (allowRotation) {
      viewer.addHandler('rotate', () => {
        const viewport = viewer.viewport;
        if (!viewport || !onRotationChange) return;
        onRotationChange(viewport.getRotation());
      });
    }

    return () => {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }
    };
  }, [iiifContent]); // Only recreate viewer when source changes

  // Update viewer state without re-initializing
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer) return;

    const viewport = viewer.viewport;
    if (!viewport) return;

    viewport.zoomTo(viewport.imageToViewportZoom(zoom), undefined, true);
    viewport.setRotation(rotation);
    viewport.setFlip(flip);
  }, [zoom, rotation, flip]);

  // Update overlays without re-initializing
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer) return;

    // Clear existing overlays
    viewer.clearOverlays();

    // Add new overlays
    overlays.forEach((overlay) => {
      viewer.addOverlay({
        element: overlay.element,
        location: new OpenSeadragon.Point(overlay.x, overlay.y),
        placement: OpenSeadragon.Placement.CENTER,
        checkResize: false,
        rotationMode: OpenSeadragon.OverlayRotationMode.NO_ROTATION,
      });
    });
  }, [overlays]);

  return (
    <div className="flex flex-col">
      <div 
        ref={viewerRef} 
        id={`controlled-openseadragon-${iiifContent}`} 
        style={{ width: "600px", maxWidth: '600px', height: '600px', maxHeight: "600px" }} 
      />
    </div>
  );
};

export default ControlledOpenSeaDragon;
