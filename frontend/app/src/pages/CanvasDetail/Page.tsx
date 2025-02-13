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
  const canvasStore = useCanvasViewer();
  const image = canvas?.images?.[0];

  if (isLoading) {
    return <p>Loading...</p>;
  }

  return (
    <div className="flex">
      <CanvasMenu />
      <div className="flex-1 flex flex-col gap-5 p-5">
      <div className="flex gap-20">
        <h2 className="flex gap-20">Canvas: {canvas.name}</h2>
      </div>
      <div className="flex w-full">
        <ControlledOpenSeaDragon 
          iiifContent={image.dzi_file} 
          canvasStore={canvasStore}
          allowZoom={true}
          allowFlip={false}
          allowRotation={false}
        />
      </div>
      </div>
    </div>
  );
};
export default CanvasDetail;
