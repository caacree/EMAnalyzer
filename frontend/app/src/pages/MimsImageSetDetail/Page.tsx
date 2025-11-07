/* eslint-disable @typescript-eslint/no-explicit-any */
import { useNavigate, useParams } from "@tanstack/react-router";
import React, { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api, { BASE_URL, API_BASE_URL, buildMediaURL } from "@/api/api";
import ControlledOpenSeaDragon from '@/components/shared/ControlledOpenSeaDragon';
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/shared/ui/tabs";
import { Checkbox } from "@/components/shared/ui/checkbox";
import { Slider } from "@/components/shared/ui/slider";
import { Trash2, XCircleIcon } from "lucide-react";
import { postImageSetPoints } from "@/api/api";
import { cn } from "@/lib/utils";
import { usePrepareCanvasForGuiQuery } from "@/queries/queries";
import CanvasMenu from "../CanvasDetail/CanvasMenu";
import RegisteredImageSet from "./RegisteredImageSet";
import UnregisteredImageSet from "./UnregisteredImageSet";


const fetchCanvasDetail = async (id: string) => {
  const res = await api.get(`canvas/${id}/`);
  return res.data;
};

const MimsImageSetDetail = () => {
  const params = useParams({ strict: false });
  const { canvasId, mimsImageSetId } = params;
  const mimsImageSet  = mimsImageSetId as string;
  const [selectedIsotope, setSelectedIsotope] = useState("32S");
  const [mode, setMode] = useState<"shapes" | "draw" | "navigate" | "points">("navigate");
  const queryClient = useQueryClient();
  const { data: canvas, isLoading } = useQuery({
    queryKey: ['canvas', canvasId as string],
    queryFn: () => fetchCanvasDetail(canvasId as string),
  });
  const navigate = useNavigate({ from: window.location.pathname });
  const canvasStoreApi = useCanvasViewer;
  const canvasStore = canvasStoreApi();
  const mimsStoreApi = useMimsViewer;
  const mimsStore = mimsStoreApi();
  const {setFlip: setMimsFlip, setRotation: setMimsRotation} = mimsStore;
  const points = {em: canvasStore.points, mims: mimsStore.points};

  const image = canvas?.images?.[0];
  usePrepareCanvasForGuiQuery(canvasId as string);

  useEffect(() => {
    if (image && mimsImageSetId) {
      const selectedMimsSet = canvas?.mims_sets?.find((imageSet: any) => imageSet.id === mimsImageSetId);
      if (!selectedMimsSet) {
        return;
      }
      const degrees = (selectedMimsSet?.rotation_degrees) % 360
      setMimsFlip(selectedMimsSet?.flip);
      setMimsRotation(selectedMimsSet?.flip ? degrees : 360 - degrees);
      if (selectedMimsSet?.composite_images) {
        setSelectedIsotope(Object.keys(selectedMimsSet?.composite_images)[0]);
      } else if (selectedMimsSet?.mims_images?.length > 0) {
        setSelectedIsotope(selectedMimsSet?.mims_images[0]?.isotopes[0]?.name);
      }
    }
  }, [canvas, mimsImageSetId]);
    
  const handleDeleteImageSet = async () => {
    try {
      await api.delete(`/mims_image_set/${mimsImageSet}/`);
      queryClient.invalidateQueries();
      // Navigate back to canvas page
      navigate({ to: `/canvas/${canvasId}` });
    } catch (error) {
      console.error('Failed to delete MIMS Image Set:', error);
      alert('Failed to delete MIMS Image Set');
    }
    setShowDeleteConfirm(false);
  };

  if (isLoading) {
    return <p>Loading...</p>;
  }

  const submitImageSetPoints = () => {
    postImageSetPoints(mimsImageSet, points, selectedIsotope).then(() => {
      canvasStore.clearPoints();
      mimsStore.clearPoints();
    })
  }  

  const selectedMimsSet = canvas?.mims_sets?.find((imageSet: any) => imageSet.id === mimsImageSet);
  const isRegistered = selectedMimsSet?.status?.toLowerCase() === 'registered';
  return (
    <div className="flex">
      <CanvasMenu />
      <div className="flex flex-col px-10 gap-5 w-full grow">
        {/* Branching logic based on registration status */}
        {isRegistered ? (
          <RegisteredImageSet 
            selectedMimsSet={selectedMimsSet}
            canvas={canvas}
            onDelete={handleDeleteImageSet}
          />
        ) : (
          <UnregisteredImageSet 
            selectedMimsSet={selectedMimsSet}
            image={image}
            selectedIsotope={selectedIsotope}
            setSelectedIsotope={setSelectedIsotope}
            mode={mode}
            setMode={setMode}
            points={points}
            canvasStoreApi={canvasStoreApi}
            mimsStoreApi={mimsStoreApi}
            mimsStore={mimsStore}
            canvasStore={canvasStore}
            setMimsFlip={setMimsFlip}
            setMimsRotation={setMimsRotation}
            submitImageSetPoints={submitImageSetPoints}
          />
        )}
      </div>
    </div>
  );
};
export default MimsImageSetDetail;
