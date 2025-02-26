import React, { useEffect, useRef } from "react";
import OpenSeadragon from 'openseadragon';
import 'openseadragon-filtering';


interface Point {
  x: number;
  y: number;
  id: string;
  type?: string;
  color?: string;
}

interface canvasStoreType {
  zoom: number;
  flip: boolean;
  rotation: number;
  coordinates?: Point[];
  overlays?: any[];
  points?: Point[];
  setZoom: (zoom: number) => void;
  setFlip: (flip: boolean) => void;
  setRotation: (rotation: number) => void;
  addPoint: (point: Point) => void;
}
interface ControlledOpenSeaDragonProps {
  iiifContent?: string;
  url?: string;
  canvasStore: canvasStoreType;
  allowPointSelection?: boolean | string;
  allowZoom?: boolean;
  allowFlip?: boolean;
  allowRotation?: boolean;
  fixed?: boolean;
}

const ControlledOpenSeaDragon: React.FC<ControlledOpenSeaDragonProps> = ({
  iiifContent,
  url,
  canvasStore,
  allowPointSelection = false,
  allowZoom = false,
  allowFlip = false,
  allowRotation = false,
  fixed = false,
}) => {
  const {
    zoom,
    flip,
    rotation,
    points,
    coordinates,
    overlays,
    setZoom,
    setFlip,
    setRotation,
    addPoint
  } = canvasStore;
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const osdViewerRef = useRef<OpenSeadragon.Viewer | null>(null);

  const newPointIndicator = (number: number, color: string, showNumber: boolean) => {
    const container = document.createElement('div');
    container.style.position = 'relative';
    container.style.zIndex = "2";
  
    const dot = document.createElement('div');
    dot.style.width = '5px';
    dot.style.height = '5px';
    dot.style.backgroundColor = color || 'red';
    dot.style.borderRadius = '50%';
    dot.style.position = 'absolute';
    dot.style.bottom = '0';
    dot.style.left = '0';
    container.appendChild(dot);
    
    if (showNumber) {
      const numberLabel = document.createElement('div');
      numberLabel.innerText = number.toString();
      numberLabel.style.color = color ||'red';
      numberLabel.style.position = 'absolute';
      numberLabel.style.top = '-10px';
      numberLabel.style.left = '10px';
      container.appendChild(numberLabel);
    }
    return container;
  }

  // Initialize viewer
  useEffect(() => {
    if (!viewerRef.current || (!iiifContent && !url)) return;

    if (osdViewerRef.current) {
      osdViewerRef.current.destroy();
    }

    osdViewerRef.current = OpenSeadragon({
      prefixUrl: '/openseadragon/images/',
      id: viewerRef.current.id,
      tileSources: [iiifContent ? { tileSource: iiifContent}  : {
        type: 'image',
        url,
        buildPyramid: false,
      }],
      gestureSettingsMouse: {
        clickToZoom: allowZoom && !allowPointSelection,
        scrollToZoom: allowZoom,
        pinchToZoom: allowZoom,
      },
      gestureSettingsTouch: {
        pinchToZoom: allowZoom
      },
      zoomPerClick: allowZoom ? 2 : 1,
      zoomPerScroll: allowZoom ? 1.2 : 1,
      zoomPerDblClickDrag: allowZoom ? 1.2 : 1,
      showNavigator: allowZoom || allowRotation,
      panHorizontal: !fixed, 
      panVertical: !fixed,
      showNavigationControl: allowZoom || allowRotation,
      showZoomControl: allowZoom,
      showRotationControl: allowRotation,
      showFlipControl: false,
      crossOriginPolicy: 'Anonymous'
    });

    const viewer = osdViewerRef.current;
    
    // Set initial coordinates if available
    if (coordinates && coordinates.length > 0) {
      viewer.addOnceHandler('open', () => {
        const tiledImage = viewer.world.getItemAt(0);
        if (!tiledImage) return;

        // Convert image coordinates to viewport coordinates
        const topLeft = tiledImage.imageToViewportCoordinates(coordinates[0].x, coordinates[0].y);
        const bottomRight = coordinates[1] 
          ? tiledImage.imageToViewportCoordinates(coordinates[1].x, coordinates[1].y)
          : tiledImage.imageToViewportCoordinates(coordinates[0].x + 1, coordinates[0].y + 1);

        const bounds = new OpenSeadragon.Rect(
          topLeft.x,
          topLeft.y,
          bottomRight.x - topLeft.x,
          bottomRight.y - topLeft.y
        );
        viewer.viewport.fitBounds(bounds, true);
        
      });
    }
    if (points?.length || overlays?.length) {
      viewer.addOnceHandler('open', () => {
        addPointsAndOverlays(viewer, points, overlays);
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
    
    
    return () => {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }
    };
  }, [iiifContent, url]);

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

  // Handle zoom and selection settings changes
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer) return;

    // Update gesture settings
    viewer.gestureSettingsMouse.clickToZoom = allowZoom && !allowPointSelection;

    // Clear existing handlers
    viewer.removeAllHandlers('zoom');
    viewer.removeAllHandlers('canvas-click');

    // Add zoom handler if enabled
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

    // Add selection handler if enabled
    if (allowPointSelection) {
      viewer.addHandler('canvas-click', (e) => {
        const viewport = viewer.viewport;
        if (!viewport) return;
        const tiledImage = viewer.world.getItemAt(0);
        if (!viewport || !tiledImage) {
          return;
        }
        const imageCoords = tiledImage.viewerElementToImageCoordinates(e.position);
        addPoint({
          id: Math.random().toString(), 
          x: imageCoords.x, 
          y: imageCoords.y, 
          type: typeof allowPointSelection === "string" ? allowPointSelection : "point",
          color: allowPointSelection === "include" ? "green" : "red"
        });
      });
      viewer.addHandler("canvas-key", (e: any) => {
        e.preventDefaultAction = true;
      });
    }
  }, [allowZoom, allowPointSelection, fixed]);

  const addPointsAndOverlays = (viewer: any, points: any, overlays: any) => {
    viewer.clearOverlays();
    
    // Add overlays with bbox as red lines
    overlays?.forEach((overlay: any) => {
      const { bbox, polygon } = overlay.data;
      if (!bbox && !polygon) return; 
      const outline = bbox || polygon;

      // Convert bbox points to viewport coordinates
      const tiledImage = viewer.world.getItemAt(0);
      if (!tiledImage) return;
      const viewportPoints = outline.map((p: number[]) =>
        tiledImage.imageToViewportCoordinates(p[0], p[1])
      );
      
      const minX = Math.min(...viewportPoints.map((p: any) => p.x));
      const minY = Math.min(...viewportPoints.map((p: any) => p.y));
      const maxX = Math.max(...viewportPoints.map((p: any) => p.x));
      const maxY = Math.max(...viewportPoints.map((p: any) => p.y));

      const svgNS = "http://www.w3.org/2000/svg";
      const svgElement = document.createElementNS(svgNS, "svg");
      svgElement.setAttribute("xmlns", svgNS);
      svgElement.setAttribute("style", "position:absolute;overflow:visible;pointer-events:none;z-index:1;width:100%;height:100%;");
      svgElement.setAttribute("width", (maxX - minX).toString());
      svgElement.setAttribute("height", (maxY - minY).toString());
      svgElement.setAttribute("viewBox", `0 0 ${maxX - minX} ${maxY - minY}`);

      // Create polyline element for connecting the points
      const polyline = document.createElementNS(svgNS, "polyline");
      const relativePoints = viewportPoints
        .map((p: any) => `${p.x - minX},${p.y - minY}`) // Convert to local coordinates within the SVG
        .join(" ");
      polyline.setAttribute("points", relativePoints + ` ${viewportPoints[0].x - minX},${viewportPoints[0].y - minY}`); // Close path
      polyline.setAttribute("stroke", overlay.fill ? "none" : (overlay.color || "red"));
      polyline.setAttribute("stroke-width", overlay.fill ? "0" :"0.01");
      polyline.setAttribute("fill", overlay.fill ? overlay.color : "none");
      polyline.setAttribute("opacity", "0.5");
      svgElement.appendChild(polyline);

      const flipScale = flip ? -1 : 1;
      svgElement.style.transformOrigin = "center";
      svgElement.style.transform = `rotate(${-rotation}deg) scale(${flipScale}, 1)`;

      const wrapper = document.createElement("div");
      wrapper.appendChild(svgElement);

      // Add the SVG overlay to the viewer
      viewer.addOverlay({
        id: overlay.id,
        element: wrapper as unknown as HTMLElement,
        location: new OpenSeadragon.Rect(
          minX,
          minY,
          maxX - minX,
          maxY - minY
        ),
        checkResize: false,
        rotationMode: OpenSeadragon.OverlayRotationMode.BOUNDING_BOX
      });
    });
    const pointObjs = points?.map((point: any, index: number) => {
      return {
        id: point.id,
        element: newPointIndicator(index + 1, point.color || 'red', true),
        px: point.x, 
        py: point.y,
        placement: 'CENTER',
        checkResize: false,
        rotationMode: OpenSeadragon.OverlayRotationMode.EXACT
      };
    });

    pointObjs?.forEach((pointObj: any) => {
      viewer.addOverlay(pointObj);
    });
  }

  // Handle points changes
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer) return;
    addPointsAndOverlays(viewer, points, overlays);
  }, [points, overlays, flip]);

  // Handle coordinates changes
  useEffect(() => {
    const viewer = osdViewerRef.current;
    if (!viewer?.viewport || !coordinates || coordinates.length === 0) return;

    const handleCoordinates = () => {
      const tiledImage = viewer.world.getItemAt(0);
      if (!tiledImage) return;

      // Convert image coordinates to viewport coordinates
      const topLeft = tiledImage.imageToViewportCoordinates(coordinates[0].x, coordinates[0].y);
      const bottomRight = coordinates[1] 
        ? tiledImage.imageToViewportCoordinates(coordinates[1].x, coordinates[1].y)
        : tiledImage.imageToViewportCoordinates(coordinates[0].x + 1, coordinates[0].y + 1);

      const bounds = new OpenSeadragon.Rect(
        topLeft.x,
        topLeft.y,
        bottomRight.x - topLeft.x,
        bottomRight.y - topLeft.y
      );
      viewer.viewport.fitBounds(bounds, true);
    };

    // Try immediately in case image is already loaded
    const tiledImage = viewer.world.getItemAt(0);
    if (tiledImage) {
      handleCoordinates();
    } else {
      // Otherwise wait for the image to load
      viewer.addOnceHandler('open', handleCoordinates);
    }

    return () => {
      viewer.removeHandler('open', handleCoordinates);
    };
  }, [coordinates]);

  return (
      <div 
        ref={viewerRef} 
        className="flex grow border"
        id={`controlled-openseadragon-${iiifContent || url}`} 
      />
  );
};

export default ControlledOpenSeaDragon
