import React, { useEffect, useRef } from "react";
import OpenSeadragon from 'openseadragon';

interface Point {
  x: number;
  y: number;
}

interface canvasStoreType {
  zoom: number;
  flip: boolean;
  rotation: number;
  points?: Point[];
  setZoom: (zoom: number) => void;
  setFlip: (flip: boolean) => void;
  setRotation: (rotation: number) => void;
  addPoint: (point: Point) => void;
}
interface ControlledOpenSeaDragonProps {
  iiifContent: string;
  canvasStore: canvasStoreType;
  allowSelection?: boolean;
  allowZoom?: boolean;
  allowFlip?: boolean;
  allowRotation?: boolean;
}

const ControlledOpenSeaDragon: React.FC<ControlledOpenSeaDragonProps> = ({
  iiifContent,
  canvasStore,
  allowSelection = false,
  allowZoom = false,
  allowFlip = false,
  allowRotation = false,
}) => {
  const {zoom,
    flip,
    rotation,
    points,
    setZoom,
    setFlip,
    setRotation,
    addPoint
  } = canvasStore;
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const osdViewerRef = useRef<OpenSeadragon.Viewer | null>(null);

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

  // Initialize viewer
  useEffect(() => {
    if (!viewerRef.current || !iiifContent) return;

    if (osdViewerRef.current) {
      osdViewerRef.current.destroy();
    }

    osdViewerRef.current = OpenSeadragon({
      prefixUrl: '/openseadragon/images/',
      id: viewerRef.current.id,
      tileSources: [{ tileSource: iiifContent }],
      minZoomLevel: 0.9,
      gestureSettingsMouse: {
        clickToZoom: allowZoom,
      },
      showNavigator: true,
      showRotationControl: allowRotation,
      showFlipControl: allowFlip,
    });

    const viewer = osdViewerRef.current;

    if (allowZoom) {
      viewer.addHandler('zoom', () => {
        const viewport = viewer.viewport;
        if (!viewport) return;
        const newZoom = viewport.viewportToImageZoom(viewport.getZoom());
        if (newZoom !== zoom) {
          setZoom(newZoom);
        }
      });
    }

    if (allowRotation) {
      viewer.addHandler('rotate', () => {
        const viewport = viewer.viewport;
        if (!viewport) return;
        const newRotation = viewport.getRotation();
        if (newRotation !== rotation) {
          setRotation(newRotation);
        }
      });
    }

    if (allowFlip) {
      viewer.addHandler('flip', () => {
        const viewport = viewer.viewport;
        if (!viewport) return;
        const newFlip = viewport.getFlip();
        if (newFlip !== flip) {
          setFlip(newFlip);
        }
      });
    }
    if (allowSelection){
      viewer.addHandler('canvas-click', (e) => {
        const viewport = viewer.viewport;
        if (!viewport) return;
        const tiledImage = viewer.world.getItemAt(0);
        if (!viewport || !tiledImage) {
          return
        }
        const imageCoords = tiledImage.viewerElementToImageCoordinates(e.position);
        addPoint({x: imageCoords.x, y: imageCoords.y});
      });
    }

    return () => {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }
    };
  }, [iiifContent]);

  // Handle zoom changes
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer?.viewport) return;

    const currentZoom = viewer.viewport.viewportToImageZoom(viewer.viewport.getZoom());
    if (currentZoom !== zoom) {
      viewer.viewport.zoomTo(viewer.viewport.imageToViewportZoom(zoom), undefined, true);
    }
  }, [zoom]);

  // Handle rotation changes
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer?.viewport) return;

    const currentRotation = viewer.viewport.getRotation();
    if (currentRotation !== rotation) {
      viewer.viewport.setRotation(rotation);
    }
  }, [rotation]);

  // Handle flip changes
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer?.viewport) return;

    const currentFlip = viewer.viewport.getFlip();
    if (currentFlip !== flip) {
      viewer.viewport.setFlip(flip);
    }
  }, [flip]);

  // Handle points changes
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer) return;

    viewer.clearOverlays();

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

export default ControlledOpenSeaDragon