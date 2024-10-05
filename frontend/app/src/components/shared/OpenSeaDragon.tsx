import React, { useEffect, useRef } from "react";
import OpenSeadragon from 'openseadragon';

const OpenSeaDragon = ({ iiifContent, options, viewerPos, onClick, points, setSavedEmPos }: 
  {iiifContent?: string; options?: object; viewerPos?: any; onClick?: any; points: any[], setSavedEmPos: any }) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const osdViewerRef = useRef<OpenSeadragon.Viewer | null>(null);
  const [currentZoom, setCurrentZoom] = React.useState<number | null>(null);
  const [currentBounds, setCurrentBounds] = React.useState<any | null>(null);
  
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
  useEffect(() => {
    if (viewerRef.current && iiifContent) {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }
      const overlays = points?.map((point: any, index) => {
        return {
          id: newPointIndicator(index+1),
          px: point.x,
          py: point.y,
          placement: 'CENTER',
          checkResize: false,
          rotationMode: OpenSeadragon.OverlayRotationMode.NO_ROTATION
        };
      })

      osdViewerRef.current = OpenSeadragon({
        prefixUrl: '/openseadragon/images/',
        id: viewerRef.current.id,
        tileSources: [{tileSource: iiifContent} as any],
        minZoomLevel: 0.9,
        overlays,
        gestureSettingsMouse: {
          clickToZoom: false,
        },
        showNavigator: true,
        ...options
      });

      osdViewerRef.current.addHandler('open', () => {
        const viewport = osdViewerRef?.current?.viewport;
        if (!viewport) {
          return
        }
        if (viewerPos?.zoom) {
          const imageZoom = viewport.imageToViewportZoom(viewerPos?.zoom)
          viewport?.zoomTo(imageZoom);
          setCurrentZoom(viewport.viewportToImageZoom(viewport.getZoom()));
        }
        
        if (viewerPos?.xOffset || viewerPos?.yOffset) {
          const viewportRect = viewport.imageToViewportRectangle(viewerPos?.xOffset, viewerPos?.yOffset, 512/viewerPos?.zoom, 512/viewerPos?.zoom);
          viewport.fitBounds(viewportRect, true);
          setCurrentBounds(viewport.viewportToImageRectangle(viewport.getBounds()));
        }
      });
      osdViewerRef.current.addHandler('pan', () => {
        const viewport = osdViewerRef?.current?.viewport;
        if (!viewport) {
          return
        }
        const newBounds = viewport.viewportToImageRectangle(viewport.getBounds());
        setCurrentBounds(newBounds);
        const zoom = currentZoom || viewport.viewportToImageZoom(viewport.getZoom());
        setSavedEmPos?.({xOffset: newBounds.x, yOffset: newBounds.y, zoom});
      });
      osdViewerRef.current.addHandler('zoom', () => {
        const viewport = osdViewerRef?.current?.viewport;
        if (!viewport) {
          return
        }
        const newZoom = viewport.viewportToImageZoom(viewport.getZoom());
        setCurrentZoom(newZoom);
        const bounds = currentBounds?.x ? currentBounds : viewport.viewportToImageRectangle(viewport.getBounds());
        setSavedEmPos?.({xOffset: bounds?.x, yOffset: bounds?.y, zoom: newZoom});
      });
      osdViewerRef.current.addHandler('canvas-click', (e) => {
        const viewport = osdViewerRef?.current?.viewport;
        const tiledImage = osdViewerRef?.current?.world.getItemAt(0);
        if (!viewport || !tiledImage) {
          return
        }
        const imageCoords = tiledImage.viewerElementToImageCoordinates(e.position);
        onClick && onClick({x: imageCoords.x, y: imageCoords.y});
      });
    }
    // Cleanup function to destroy the viewer when the component unmounts or iiifContent changes
    return () => {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }
    };
  }, [iiifContent, options, points, viewerPos]);

  return (
    <div className="flex flex-col">
      <div ref={viewerRef} id={`openseadragon${iiifContent}`} style={{ width: "600px", maxWidth: '600px', height: '600px', maxHeight: "600px" }} />
    </div>
  );
};

export default OpenSeaDragon;