/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react";
import { Link } from "@tanstack/react-router";
import api from "../../api/api";
import { TrashIcon } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useCanvasViewer } from "@/stores/canvasViewer";


const MIMSImageSet = ({ mimsImageSet, onSelect }: { mimsImageSet: any, onSelect: any }) => {
  const queryClient = useQueryClient();
  const handleDeleteMimsSet = (imageSetId: string) => {
    api.delete(`/mims_image_set/${imageSetId}/`).then(() => queryClient.invalidateQueries());
  };
  const canvasStore = useCanvasViewer();

  const updateHoverImg = (hoveredId: string | null) => {
    canvasStore.overlays.filter(overlay => overlay.data?.type === "hover").forEach(overlay => {
      canvasStore.removeOverlay(overlay.id);
    });
    if (hoveredId) {
      const hoverImgBbox = mimsImageSet.mims_images.find((mimsImage: any) => mimsImage.id === hoveredId)?.canvas_bbox;
      if (hoverImgBbox) {
        const newOverlay = {
          id: hoveredId,
          visible: true,
          data: {
            type: "hover",
            bbox: hoverImgBbox,
        }
      };
      canvasStore.addOverlay(newOverlay);
      }
    }
  };

  return (
    <div 
      className="flex items-center justify-between px-2 py-1 hover:bg-gray-800 rounded cursor-pointer"
      onClick={() => onSelect(mimsImageSet.id)}
    >
      <span>{mimsImageSet.name || mimsImageSet.id}</span>
      <button 
        onClick={(e) => {
          e.stopPropagation();
          handleDeleteMimsSet(mimsImageSet.id);
        }}
        className="opacity-50 hover:opacity-100"
      >
        <TrashIcon size={16} />
      </button>
    </div>
  );
};


export default MIMSImageSet;
