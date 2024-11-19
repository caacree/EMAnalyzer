import React, { useEffect, useRef } from "react";
import OpenSeadragon from 'openseadragon';

interface Point {
  x: number;
  y: number;
}

interface ControlledOpenSeaDragonProps {
  iiifContent: string;
  zoom: number;
  flip: boolean;
  rotation: number;
  points?: Point[];
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

    const newPointIndicator = (number: number) => {
      const container = document.createElement('div');
      container.style.position = 'relative';
    
      const dot = document.createElement('div');
      dot.style.width = '5px';
      dot.style.height = '5px';
      dot.style.backgroundColor = 'red';
      dot.style.borderRadius = '50%';
      dot.style.position = 'absolute';
      dot.style.bottom = '0';
      dot.style.left = '0';
    
      const numberLabel = document.createElement('div');
      numberLabel.innerText = number.toString();
      numberLabel.style.color = 'red';
      numberLabel.style.position = 'absolute';
      numberLabel.style.top = '-10px';
      numberLabel.style.left = '10px';
    
      container.appendChild(dot);
      container.appendChild(numberLabel);
    
      return container;
    }

    const overlays = points?.map((point, index) => ({
      element: newPointIndicator(index + 1),
      location: new OpenSeadragon.Point(point.x, point.y),
      placement: OpenSeadragon.Placement.CENTER,
      checkResize: false,
      rotationMode: OpenSeadragon.OverlayRotationMode.NO_ROTATION,
    })) || [];

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

  // Update points without re-initializing
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer) return;

    // Clear existing overlays
    viewer.clearOverlays();

    // Add new points
    points?.forEach((point, index) => {
      viewer.addOverlay({
        element: newPointIndicator(index + 1),
        location: new OpenSeadragon.Point(point.x, point.y),
        placement: OpenSeadragon.Placement.CENTER,
        checkResize: false,
        rotationMode: OpenSeadragon.OverlayRotationMode.NO_ROTATION,
      });
    });
  }, [points]);

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
