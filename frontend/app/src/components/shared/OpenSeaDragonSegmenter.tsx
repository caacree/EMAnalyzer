import React, { useEffect, useRef } from "react";
import OpenSeadragon from 'openseadragon';
import {initSvgOverlay} from '@/components/shared/OpenSeaDragonSvgOverlay';
import api from "../../api/api";
import { useParams } from "@tanstack/react-router";
import * as d3 from 'd3';

const OpenSeaDragonSegmenter = ({ urls, isotope, shapes, onShapeSelect, options }: 
  {urls: any; isotope: any; shapes: any[]; onShapeSelect: any; options?: any; }) => {
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const osdViewerRef = useRef<OpenSeadragon.Viewer | null>(null);
  const { mimsImageId } = useParams({ strict: false });
  const [isInclude, setIsInclude] = React.useState<boolean>(true);
  const [includePoints, setIncludePoints] = React.useState<any[]>([]);
  const [excludePoints, setExcludePoints] = React.useState<any[]>([]);
  const [suggestedShape, setSuggestedShape] = React.useState<any>([]);
  
  // Keydown event handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'i') {
        setIsInclude(true);
      } else if (e.key === 'o') {
        setIsInclude(false);
      } else if (e.key === "r") {
        setIsInclude(true);
        setIncludePoints([]);
        setExcludePoints([]); 
        setSuggestedShape([]);
      } else if (e.key === ' ') {
        // Prevent default spacebar behavior (scrolling)
        e.preventDefault();
        // Pass the suggested shape and reset it
        if (suggestedShape.length > 0) {
          setSuggestedShape([]);
          setIsInclude(true);
          setIncludePoints([]);
          setExcludePoints([]);
          onShapeSelect(suggestedShape);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    // Cleanup the event listener when the component unmounts
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [suggestedShape, onShapeSelect]);

  useEffect(() => {
    if (viewerRef.current && url) {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }

      osdViewerRef.current = OpenSeadragon({
        prefixUrl: '/openseadragon/images/',
        id: viewerRef.current.id,
        tileSources: {
          type: 'image',
          url,
        },
        defaultZoomLevel: 0,
        zoomPerClick: 1,
        zoomPerScroll: 1,
        zoomPerDblClickDrag: 1,
        showZoomControl: false,
        showHomeControl: false,
        showFullPageControl: false,
        showRotationControl: false,
        rotationIncrement: 0,
        panHorizontal: false,
        panVertical: false,
        gestureSettingsMouse: {
          clickToZoom: false,
        },
        showNavigator: false,
        ...options
      });
      osdViewerRef.current.addHandler('canvas-key', (e) => {
        e.preventDefaultAction = true;
      });
      osdViewerRef.current.addHandler('canvas-click', canvasClickHandler);
      osdViewerRef.current.addHandler('open', () => {
        setOverlays();
      });
    }

    // Cleanup function to destroy the viewer when the component unmounts or iiifContent changes
    return () => {
      if (osdViewerRef.current) {
        osdViewerRef.current.destroy();
      }
    };
  }, [urls, onShapeSelect, shapes]);

  const canvasClickHandler = (e: any) => {
    const viewport = osdViewerRef?.current?.viewport;
    const tiledImage = osdViewerRef?.current?.world.getItemAt(0);
    if (!viewport || !tiledImage) {
      return
    }
    const imageCoords = tiledImage.viewerElementToImageCoordinates(e.position);
    if (isInclude) {
      setIncludePoints([...includePoints, {x: imageCoords.x, y: imageCoords.y}]);
    } else {
      setExcludePoints([...excludePoints, {x: imageCoords.x, y: imageCoords.y}]);
    }
  };

  useEffect(() => {
    if (!osdViewerRef.current) {
      return 
    }
    osdViewerRef.current?.removeAllHandlers('canvas-click');
    osdViewerRef.current?.addHandler('canvas-click', canvasClickHandler);
    const point_coords: any = []
    const point_labels: any = [];
    includePoints?.forEach((point) => {
      point_coords.push([point.x, point.y]);
      point_labels.push(1);
    })
    excludePoints?.forEach((point) => {
      point_coords.push([point.x, point.y]);
      point_labels.push(0);
    })
    if (point_coords.length === 0) {
      return;
    }
    api.post(`mims_image/${mimsImageId}/get_segment_prediction/`, 
      {image_key: isotope, point_coords, point_labels}).then((res) => {
        setSuggestedShape(res.data?.polygons);
    })
    
  }, [includePoints, excludePoints, isInclude]);

  const addPolygonEl = (overlay: any, polygon: any, color: string) => {
    const tiledImage = osdViewerRef?.current?.world?.getItemAt(0);
    const points = polygon.map(([x, y]: number[]) => {
      const imgCoords = tiledImage?.imageToViewportCoordinates(x, y);
      return `${imgCoords?.x},${imgCoords?.y}`;
    }).join(" ");
    d3.select(overlay.node()).append("polygon")
    .attr("points", points)
    .style("fill", color)
    .style("stroke-width", "0");
  }

  const setOverlays = () => {
    if (!osdViewerRef.current) {
      return;
    }
    osdViewerRef.current.clearOverlays();
    const overlay = initSvgOverlay(osdViewerRef.current);
    d3.select(overlay.node()).selectAll("polygon").remove();
    d3.select(overlay.node()).selectAll("circle").remove();
    d3.select(overlay.node()).selectAll("line").remove();
    d3.select(overlay.node()).selectAll("path").remove();
    shapes.forEach((polygonEls: any[]) => {
      polygonEls.forEach((polygonEl: any) => {
        addPolygonEl(overlay, polygonEl, "#0000FF");
      });
    });
    suggestedShape?.forEach((polygonEl: any) => {
      addPolygonEl(overlay, polygonEl, "rgba(0, 255, 0, 0.5)");
    });
    includePoints?.forEach((point) => {
      const location = osdViewerRef.current?.viewport?.imageToViewportCoordinates(new OpenSeadragon.Point(point.x, point.y));
      d3.select(overlay.node()).append("circle").attr("cx", location?.x).attr("cy", location?.y).attr("r", 0.005).style("fill", "#FF0000");
    });
    excludePoints?.forEach((point) => {
      const location: any = osdViewerRef.current?.viewport?.imageToViewportCoordinates(new OpenSeadragon.Point(point.x, point.y));
      const size = 0.01; // Adjust the size of the "X" as needed

      // Draw the first diagonal line of the "X"
      d3.select(overlay.node())
        .append("line")
        .attr("x1", location?.x - size)
        .attr("y1", location?.y - size)
        .attr("x2", location?.x + size)
        .attr("y2", location?.y + size)
        .style("stroke", "#FF0000")
        .style("stroke-width", 0.002);

      // Draw the second diagonal line of the "X"
      d3.select(overlay.node())
        .append("line")
        .attr("x1", location?.x - size)
        .attr("y1", location?.y + size)
        .attr("x2", location?.x + size)
        .attr("y2", location?.y - size)
        .style("stroke", "#FF0000")
        .style("stroke-width", 0.002);
    });
  }

  useEffect(() => {
    setOverlays();
  }, [includePoints, excludePoints, suggestedShape]);

  const url = 'http://localhost:8000/'+urls?.[`${isotope}_url`];
  if (!isotope) {
    return null;
  }

  return (
    <div className="flex flex-col">
      <div ref={viewerRef} id={`openseadragon${url}`} style={{ width: "600px", maxWidth: '600px', height: '600px', maxHeight: "600px" }} />
    </div>
  );
};

export default OpenSeaDragonSegmenter;