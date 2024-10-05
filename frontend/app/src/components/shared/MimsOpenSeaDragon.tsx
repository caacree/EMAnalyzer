import React, { useEffect, useRef } from "react";
import OpenSeadragon from 'openseadragon';

const OpenSeaDragon = ({ url, options, onClick, iiifContent, allowZoom = false, points }: {url?: string; options?: object; onClick?: any; iiifContent?: string, allowZoom?: boolean; points?: any[]}) => {
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
  useEffect(() => {
    if (viewerRef.current && (url || iiifContent)) {
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
        };
      })
      osdViewerRef.current = OpenSeadragon({
        prefixUrl: '/openseadragon/images/',
        id: viewerRef.current.id,
        tileSources: iiifContent ? [{tileSource: iiifContent} as any] : ({
          type: 'image',
          url,
        }),
        overlays,
        showNavigator: false,
        showZoomControl: allowZoom,
        zoomPerClick: allowZoom ? 1.5 : 1,
        zoomPerScroll: allowZoom ? 1.2 : 1,
        zoomPerSecond: allowZoom ? 1.5 : 1,
        showHomeControl: false,
        showFullPageControl: false,
        ...options
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
  }, [url, iiifContent, options, points]);

  return <div ref={viewerRef} id={`openseadragon${url || iiifContent}`} style={{ width: '600px', maxWidth: '600px', height: '600px', maxHeight: "600px" }} />;
};

export default OpenSeaDragon;