import React from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/api";

const fetchCanvasDetail = async (id: string) => {
  const res = await api.get(`canvas/${id}/`);
  return res.data;
};
const CanvasMenu = () => {
  const { canvasId } = useParams({ strict: false});
  const { data: canvas } = useQuery({
    queryKey: ['canvas', canvasId as string],
    queryFn: () => fetchCanvasDetail(canvasId as string),
  });
  
  return (
    <div className="w-64 bg-gray-900 h-screen p-4 text-white ">
      <nav className="space-y-2">
        <div className="flex gap-20">
          <h2 className="flex gap-20">Canvas: {canvas.name}</h2>
        </div>
        <Link 
          to={`/canvas/${canvasId}`}
          className="block px-4 py-2 text-white hover:bg-gray-800 rounded"
        >
          Segmentations
        </Link>
        <Link 
          to={`/canvas/${canvasId}`}
          className="block px-4 py-2 text-white hover:bg-gray-800 rounded"
        >
          Correlative
        </Link>
      </nav>
    </div>
  );
};

export default CanvasMenu;
