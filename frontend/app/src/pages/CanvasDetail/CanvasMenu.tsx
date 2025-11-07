import React, { useState, useEffect } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { fetchSegmentationFiles, deleteSegmentationFile, fetchSegmentationProgress, fetchSegmentedObjects, updateCanvas } from "@/api/api";
import MIMSImageSetMenuItem from "./MimsImageSetListMenuItem";
import MimsImageSetUploadModal from "@/components/shared/MimsImageSetUploadModal";
import SegmentationUploadModal from "@/components/shared/SegmentationUploadModal";
import RenameModal from "@/components/shared/RenameModal";
import { PlusCircle, Trash2, FileText, Eye, EyeOff, Loader2, Pencil } from "lucide-react";
import { useCanvasViewer } from "@/stores/canvasViewer";

const fetchCanvasDetail = async (id: string) => {
  const res = await api.get(`canvas/${id}/`);
  return res.data;
};

const CanvasMenu = () => {
  const params = useParams({ strict: false});
  const { canvasId, mimsImageSetId } = params;
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isSegmentationModalOpen, setIsSegmentationModalOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [selectedSegmentation, setSelectedSegmentation] = useState<string | null>(null);
  const canvasStore = useCanvasViewer();
  const queryClient = useQueryClient();
  
  const { data: canvas } = useQuery({
    queryKey: ['canvas', canvasId as string],
    queryFn: () => fetchCanvasDetail(canvasId as string),
  });
  
  const { data: segmentations, refetch: refetchSegmentations } = useQuery({
    queryKey: ['segmentations', canvasId],
    queryFn: () => fetchSegmentationFiles(canvasId as string),
    enabled: !!canvasId,
    refetchInterval: (data) => {
      // Poll every 2 seconds if any segmentation is processing
      if (!data || !Array.isArray(data)) return false;
      const hasProcessing = data.some((seg: any) => seg.status === 'processing');
      return hasProcessing ? 2000 : false;
    },
  });
  
  // Poll for progress updates for processing segmentations
  useEffect(() => {
    
    const processingSegmentations = segmentations?.filter((seg: any) => seg.status === 'processing');
    if (processingSegmentations?.length === 0) return;
    
    const pollProgress = async () => {
      for (const seg of processingSegmentations) {
        try {
          await fetchSegmentationProgress(seg.id);
        } catch (error) {
          console.error('Error fetching progress:', error);
        }
      }
      // Refetch the list to update the UI
      refetchSegmentations();
    };
    
    const interval = setInterval(pollProgress, 2000);
    return () => clearInterval(interval);
  }, [segmentations, refetchSegmentations]);
  
  const deleteSegmentationMutation = useMutation({
    mutationFn: deleteSegmentationFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['segmentations', canvasId] });
    },
  });

  const updateCanvasMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      updateCanvas(id, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['canvas', canvasId] });
    },
  });
  
  const handleRenameCanvas = (newName: string) => {
    updateCanvasMutation.mutate({ id: canvasId as string, name: newName });
  };

  const handleSegmentationClick = (segId: string) => {
    // Toggle selection - only one segmentation visible at a time
    if (selectedSegmentation === segId) {
      setSelectedSegmentation(null);
      canvasStore.setSegmentationOverlays([]);
    } else {
      setSelectedSegmentation(segId);
      // Load the segmentation objects
      loadSegmentationObjects(segId);
    }
  };
  
  const loadSegmentationObjects = async (segmentationId: string) => {
    try {
      const segFile = segmentations?.find((s: any) => s.id === segmentationId);
      if (!segFile) return;
      
      // Fetch the segmented objects for this file
      const objects = await fetchSegmentedObjects(canvasId as string, segmentationId);
      
      // Convert to overlay format
      const overlays = objects.map((obj: any) => {
          const bbox = [[obj.bbox[0], obj.bbox[1]], [obj.bbox[2], obj.bbox[1]], [obj.bbox[2], obj.bbox[3]], [obj.bbox[0], obj.bbox[3]]];
          return ({
          id: `seg_${obj.id}`,
          data: { polygon: obj.polygon, bbox: bbox },
          color: "red",
          type: "segmentation",
          fill: true,
          visible: true,
          opacity: 0.5
        })
      });
      
      console.log(`Loaded ${overlays.length} segmentation overlays`);
      
      // Set the overlays in the store
      canvasStore.setSegmentationOverlays(overlays);
    } catch (error) {
      console.error('Error loading segmentation objects:', error);
    }
  };
  
  return (
    <div className="w-64 bg-gray-900 h-screen overflow-scroll p-2 text-white">
      <nav className="space-y-4">
        <div className="mb-4">
          <div className="flex items-center justify-between">
            <Link
              to={`/canvas/${canvasId}`}
              onClick={() => canvasStore.setCoordinates([])}
              className="flex-1"
            >
              <h2 className="text-lg font-semibold">Canvas: {canvas?.name}</h2>
            </Link>
            <button
              onClick={() => setIsRenameModalOpen(true)}
              className="ml-2 text-gray-400 hover:text-white"
              title="Rename canvas"
            >
              <Pencil size={16} />
            </button>
          </div>
        </div>
        
        {/* Show Segmentations section only when viewing a MimsImageSet */}
          <div className="space-y-2">
            <h3 className="text-sm uppercase tracking-wider text-gray-400">Segmentations</h3>
            <div className="pl-2 space-y-2">
              <button 
                onClick={() => setIsSegmentationModalOpen(true)}
                className="flex items-center text-sm text-gray-900 hover:text-white"
              >
                <PlusCircle size={16} className="mr-1" />
                Add Segmentation
              </button>
              
              {/* List existing segmentations */}
              {segmentations?.map((seg: any) => (
                <div 
                  key={seg.id}
                  className="flex flex-col text-sm text-gray-300 hover:text-white py-1"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center flex-1">
                      <button
                        onClick={() => handleSegmentationClick(seg.id)}
                        className="mr-2"
                        disabled={seg.status !== 'completed'}
                      >
                        {selectedSegmentation === seg.id ? (
                          <Eye size={14} className="text-blue-400" />
                        ) : (
                          <EyeOff size={14} className={seg.status === 'completed' ? '' : 'opacity-50'} />
                        )}
                      </button>
                      {seg.status === 'processing' ? (
                        <Loader2 size={14} className="mr-1 animate-spin" />
                      ) : (
                        <FileText size={14} className="mr-1" />
                      )}
                      <span className="truncate">{seg.name}</span>
                      {seg.status === 'processing' && (
                        <span className="ml-1 text-yellow-500 text-xs">
                          ({seg.progress || 0}%)
                        </span>
                      )}
                      {seg.status === 'completed' && seg.object_count > 0 && (
                        <span className="ml-1 text-green-500 text-xs">
                          ({seg.object_count})
                        </span>
                      )}
                      {seg.status === 'failed' && (
                        <span className="ml-1 text-red-500 text-xs">(failed)</span>
                      )}
                    </div>
                    <button
                      onClick={() => {
                        if (window.confirm(`Delete segmentation "${seg.name}"?`)) {
                          deleteSegmentationMutation.mutate(seg.id);
                        }
                      }}
                      className="ml-2 hover:text-red-400"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  {seg.status === 'processing' && (
                    <div className="mt-1 ml-6">
                      <div className="w-full bg-gray-700 rounded-full h-1.5">
                        <div 
                          className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${seg.progress || 0}%` }}
                        />
                      </div>
                      {seg.progress_message && (
                        <p className="text-xs text-gray-400 mt-1">{seg.progress_message}</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
              
              {segmentations?.length === 0 && (
                <p className="text-xs text-gray-500 italic">No segmentations yet</p>
              )}
            </div>
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

      <SegmentationUploadModal
        isOpen={isSegmentationModalOpen}
        onClose={() => setIsSegmentationModalOpen(false)}
        canvasId={canvasId as string}
      />

      <RenameModal
        isOpen={isRenameModalOpen}
        onClose={() => setIsRenameModalOpen(false)}
        currentName={canvas?.name || ''}
        onSubmit={handleRenameCanvas}
      />

    </div>
  );
};

export default CanvasMenu;
