/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams } from "@tanstack/react-router";
import React from "react";
import CanvasMenu from "./CanvasMenu";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/api";
import ControlledOpenSeaDragon from '@/components/shared/ControlledOpenSeaDragon';
import { useCanvasViewer } from "@/stores/canvasViewer";

const fetchCanvasDetail = async (id: string) => {
  const res = await api.get(`canvas/${id}/`);
  return res.data;
};

const CanvasDetail = () => {
  const params = useParams({ strict: false });
  const { canvasId } = params;
  const { data: canvas, isLoading } = useQuery({
    queryKey: ['canvas', canvasId as string],
    queryFn: () => fetchCanvasDetail(canvasId as string),
  });
  const canvasStore = useCanvasViewer;
  const image = canvas?.images?.[0];

  if (isLoading) {
    return <p>Loading...</p>;
  }
  //reduce them into a single array of objects with url, name, bounds
  const geotiffs = canvas?.mims_sets?.map(i => i.mims_overlays.map(o => ({
    url: o.mosaic,
    name: o.isotope,
    bounds: i.canvas_bbox
  }))).flat();

  return (
    <div className="flex grow">
      <CanvasMenu />
      <div className="flex-1 flex flex-col gap-5 p-5 grow">
        <ControlledOpenSeaDragon 
          iiifContent={image.dzi_file}
          geotiffs={geotiffs}
          canvasStore={canvasStore}
          mode="navigate"
        />
      </div>
    </div>
  );
};
export default CanvasDetail;
