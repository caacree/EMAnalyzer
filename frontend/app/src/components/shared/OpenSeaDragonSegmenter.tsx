import React, { useEffect} from "react";
import api from "../../api/api";
import { useParams } from "@tanstack/react-router";
import ControlledOpenSeaDragon from "./ControlledOpenSeaDragon";

const OpenSeaDragonSegmenter = ({ url, iiifContent, canvasStore, isotope }: 
  {url?: any; iiifContent?: any; canvasStore?: any; isotope?: any; }) => {
  
  const { mimsImageId } = useParams({ strict: false });
  const [isInclude, setIsInclude] = React.useState<boolean>(true);
  
  // Keydown event handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'i') {
        setIsInclude(true);
      } else if (e.key === 'o') {
        setIsInclude(false);
      } else if (e.key === "r") {
        setIsInclude(true);
        canvasStore.clearPoints();
        const sugs = canvasStore.overlays.filter((o: any) => o.type === "suggestion");
        sugs.forEach((o: any) => canvasStore.removeOverlay(o.id));
      } else if (e.key === ' ') {
        // Prevent default spacebar behavior (scrolling)
        e.preventDefault();
        canvasStore.clearPoints();
        const shape = canvasStore.overlays.find((p: any) => p.type === "suggestion");
        if (shape) {
          canvasStore.removeOverlay(shape.id);
          canvasStore.addOverlay({...shape, color: "green", type: "shape_confirmed"});
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [canvasStore.overlays, canvasStore.points]);
  useEffect(() => {
    if (canvasStore.points.length === 0) return;
    const point_coords = canvasStore.points.map((point: any) => [point.x, point.y]);
    const point_labels = canvasStore.points.map((point: any) => point.type === "include" ? 1 : 0);
    api.post(`mims_image/${mimsImageId}/get_segment_prediction/`, 
      {image_key: isotope, point_coords, point_labels}).then((res) => {
        canvasStore.overlays.filter((o: any) => o.type === "suggestion").forEach((o: any) => canvasStore.removeOverlay(o.id));
        canvasStore.addOverlay({id: Math.random().toString(), data: {polygon: res.data?.polygons[0]}, fill: true, color: "red", type: "suggestion"});
    })
  }, [canvasStore.points.length])

  return (
    <ControlledOpenSeaDragon
      iiifContent={iiifContent}
      url={url}
      canvasStore={canvasStore}
      allowPointSelection={isInclude ? "include" : "exclude"}
      fixed={true}
    />
  );
};

export default OpenSeaDragonSegmenter;
