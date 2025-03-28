import React, { useState } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/api";
import MIMSImageSetMenuItem from "./MimsImageSetListMenuItem";
import MimsImageSetUploadModal from "@/components/shared/MimsImageSetUploadModal";
import { PlusCircle } from "lucide-react";

const fetchCanvasDetail = async (id: string) => {
  const res = await api.get(`canvas/${id}/`);
  return res.data;
};

const CanvasMenu = () => {
  const { canvasId } = useParams({ strict: false});
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const { data: canvas } = useQuery({
    queryKey: ['canvas', canvasId as string],
    queryFn: () => fetchCanvasDetail(canvasId as string),
  });
  
  return (
    <div className="w-64 bg-gray-900 h-screen overflow-scroll p-2 text-white">
      <nav className="space-y-4">
        <div className="mb-4">
          <Link to={`/canvas/${canvasId}`}><h2 className="text-lg font-semibold">Canvas: {canvas?.name}</h2></Link>
        </div>
        
        <div className="space-y-2">
          <h3 className="text-sm uppercase tracking-wider text-gray-400">Segmentations</h3>
        </div>

        <div className="space-y-2">
          <h3 className="text-sm uppercase tracking-wider text-gray-400">Correlative</h3>
          <div className="pl-2 space-y-2">
            <button 
              onClick={() => setIsUploadModalOpen(true)}
              className="flex items-center text-sm text-gray-900"
            >
              <PlusCircle size={16} className="mr-1" />
              Add MIMS Image Set
            </button>
            {canvas?.mims_sets?.map((mimsImageSet: any) => (
                <MIMSImageSetMenuItem
                  key={mimsImageSet.id}
                  mimsImageSet={mimsImageSet}
                  onSelect={(newId: string) => {
                    window.location.href = `/canvas/${canvasId}/mimsImageSet/${newId}`;
                  }}
                />
            ))}
          </div>
        </div>
      </nav>
      
      <MimsImageSetUploadModal 
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        canvasId={canvasId as string}
      />
    </div>
  );
};

export default CanvasMenu;
