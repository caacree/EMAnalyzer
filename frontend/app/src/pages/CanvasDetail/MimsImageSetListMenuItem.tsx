/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import api from "../../api/api";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useCanvasViewer } from "@/stores/canvasViewer";
import * as Tooltip from '@radix-ui/react-tooltip';


const MIMSImageSet = ({ mimsImageSet, onSelect }: { mimsImageSet: any, onSelect: any }) => {
  const queryClient = useQueryClient();
  const [isExpanded, setIsExpanded] = useState(false);
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

  useEffect(() => {
    const isRegistered = mimsImageSet?.status.toLowerCase() === 'registered';
    setIsExpanded(!isRegistered);
  }, [mimsImageSet]);

  return (
      <div className="flex flex-col gap-2">
      <div 
        className="flex items-center justify-between px-2 py-1 hover:bg-gray-800 rounded"
      >
      <Tooltip.Provider delayDuration={100}>
        <Tooltip.Root>
          <Tooltip.Trigger asChild>
            <div className="flex items-center gap-2 truncate">
              <span onClick={() => onSelect(mimsImageSet.id)} className="truncate cursor-pointer">{mimsImageSet.name || mimsImageSet.id}</span>
              <button 
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-gray-400 hover:text-gray-300 cursor-pointer bg-transparent border-none"
              >
                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
            </div>
          </Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content
              className="bg-gray-700 text-white px-3 py-1 rounded text-sm"
              sideOffset={5}
            >
              MIMS Image set of {mimsImageSet.mims_images?.length || 0} ROI's
              <Tooltip.Arrow className="fill-gray-700" />
            </Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
        </Tooltip.Provider>
        
      </div>
      {isExpanded ? (
        <div className="pl-4 mt-2 space-y-1">
          {mimsImageSet.mims_images?.sort((a: any, b: any) => {
            const a_priority = STATUS_PRIORITY_MAP[a.status as string];
            const b_priority = STATUS_PRIORITY_MAP[b.status as string];
            return (a_priority <= b_priority ? -1 : 1); 
          }).map((mimsImage: any) => (
            <div key={mimsImage.id} className="flex items-center gap-2 text-sm" onMouseEnter={() => updateHoverImg(mimsImage.id)} onMouseLeave={() => updateHoverImg(null)}>
              <Link 
                to={`/mims_image/${mimsImage.id}`} 
                disabled={mimsImage.status === "OUTSIDE_CANVAS"}
                onClick={() => updateHoverImg(null)}
                className="truncate hover:text-blue-300"
              >
                  {extractFileName(mimsImage.file)}
              </Link>
              <span className="text-gray-400 text-xs">{mimsImage.status}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const extractFileName = (url: string) => {
  const parts = url.split('/');
  const fileName = parts[parts.length - 1];
  return fileName.split('.')[0]; // remove extension
};
const STATUS_PRIORITY_MAP: { [key: string]: number } = {
  "NEED_USER_ALIGNMENT": -2,
  "USER_ROUGH_ALIGNMENT": 2,
  "REGISTERING": 5,
  "NO_CELLS": 6,
  "DEWARP PENDING": 3,
  "AWAITING_REGISTRATION": -1,
  "OUTSIDE_CANVAS": 9
}
export default MIMSImageSet;
