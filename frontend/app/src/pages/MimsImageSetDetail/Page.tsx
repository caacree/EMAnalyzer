/* eslint-disable @typescript-eslint/no-explicit-any */
import { useNavigate, useParams } from "@tanstack/react-router";
import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/api";
import MimsImageSetUploadModal from "@/components/shared/MimsImageSetUploadModal";
import ControlledOpenSeaDragon from '@/components/shared/ControlledOpenSeaDragon';
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";
import MIMSImageSet from "../CanvasDetail/MimsImageSetListMenuItem";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/shared/ui/tabs";
import { Checkbox } from "@/components/shared/ui/checkbox";
import { Slider } from "@/components/shared/ui/slider";
import { XCircleIcon } from "lucide-react";
import { postImageSetPoints } from "@/api/api";
import { cn } from "@/lib/utils";
import { usePrepareCanvasForGuiQuery } from "@/queries/queries";
import CanvasMenu from "../CanvasDetail/CanvasMenu";

const fetchCanvasDetail = async (id: string) => {
  const res = await api.get(`canvas/${id}/`);
  return res.data;
};

const MimsImageSetDetail = () => {
  const params = useParams({ strict: false });
  const { canvasId, mimsImageSetId } = params;
  const mimsImageSet  = mimsImageSetId as string;
  const [selectedIsotope, setSelectedIsotope] = useState("32S");
  const { data: canvas, isLoading } = useQuery({
    queryKey: ['canvas', canvasId as string],
    queryFn: () => fetchCanvasDetail(canvasId as string),
  });
  const navigate = useNavigate({ from: window.location.pathname });
  const canvasStore = useCanvasViewer();
  const mimsStore = useMimsViewer();
  const {setFlip: setMimsFlip, setRotation: setMimsRotation} = mimsStore;
  const [isSelectingPoints, setIsSelectingPoints] = useState(false);
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
    
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  

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
  console.log("selectedMimsSet", selectedMimsSet)
  return (
    <div className="flex">
      <CanvasMenu />
    <div className="flex flex-col px-10 gap-5 w-full grow">
      <div className="flex w-full grow">
        <div className="flex w-1/2 max-w-1/2 min-h-[400px] grow">
          <ControlledOpenSeaDragon 
            iiifContent={image.dzi_file} 
            canvasStore={canvasStore}
            allowZoom={true}
            allowFlip={false}
            allowRotation={false}
            allowPointSelection={isSelectingPoints}
          />
        </div>
        <div className="flex w-1/2 max-w-1/2">
          <div className={cn("flex flex-col grow gap-3 max-w-full overflow-hidden min-h-[400px]")}>
            {!mimsImageSet ? (
              <>
                <div>MIMS Image sets</div>
                {canvas?.mims_sets?.map((mimsImageSet: any) => (
                    <MIMSImageSet key={mimsImageSet.id} mimsImageSet={mimsImageSet} onSelect={(newId: string) => {
                    navigate({ search: (prev: any) => ({ ...prev, mimsImageSet: newId }) });
                  }} />
                ))}
              </>
            ) : null}
            {selectedMimsSet ? (
                <Tabs defaultValue={selectedIsotope} className="flex flex-col grow">
                  <TabsList className="flex space-x-1">
                    {selectedMimsSet.mims_images?.[0].isotopes.map((isotope: any) => (
                      <TabsTrigger key={isotope.id} value={isotope.name} onClick={() => setSelectedIsotope(isotope.name)}>
                        {isotope.name}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  {selectedMimsSet.mims_images?.[0].isotopes.map((isotope: any) => {
                    const isActive = selectedIsotope === isotope.name;
                    let iiifContent, url = undefined;
                    if (selectedMimsSet.mims_images.length > 1) {
                      iiifContent = "http://localhost:8000" + selectedMimsSet.composite_images[isotope]+"/info.json"
                    } else {
                      url = `http://localhost:8000/api/mims_image/${selectedMimsSet.mims_images[0].id}/image.png?species=${isotope.name}&autocontrast=true`
                    }
                    return (
                    <TabsContent key={isotope.id} value={isotope.name} className={cn("flex flex-col", isActive ? "grow" : "hidden")}>
                      <div className="flex items-center justify-between">
                        <div className="flex gap-2 items-center">
                          Flip: <Checkbox checked={mimsStore.flip} onCheckedChange={setMimsFlip} />
                        </div>
                        <div className="flex gap-2 items-center">
                          Rotation:<Slider 
                            value={[mimsStore.rotation]} 
                            min={0} 
                            max={360} 
                            onValueChange={(val) => setMimsRotation(Math.round(val[0]))} 
                          />{mimsStore.rotation}&deg;
                        </div>
                      </div>
                      <div className="flex grow">
                        <ControlledOpenSeaDragon 
                        iiifContent={iiifContent}
                        url={url}
                        canvasStore={mimsStore}
                          allowZoom={true}
                          allowFlip={true}
                          allowRotation={true}
                          allowPointSelection={isSelectingPoints}
                        />
                      </div>
                    </TabsContent>
                  )})}
                </Tabs>
            ) : null}
            <button
              onClick={() => setIsUploadModalOpen(true)}
              className="bg-blue-500 text-white px-4 py-2 rounded flex items-center justify-center"
            >
              Add New MIMS Image Set
            </button>
            <MimsImageSetUploadModal 
              isOpen={isUploadModalOpen}
              onClose={() => setIsUploadModalOpen(false)}
              canvasId={canvas.id}
            />
          </div>
        </div>
      </div>
      {selectedMimsSet ? (
        <div className="flex flex-col">
          <div className="flex gap-2 items-center">
            <div>Select points</div>
            <Checkbox checked={isSelectingPoints} onCheckedChange={setIsSelectingPoints} />
          </div>
          <div>Selected Points</div>
          {[...Array(Math.max(points.em?.length, points.mims?.length))].map((_, index) => {
            if (!points.em[index] && !points.mims[index]) {
              return null;
            }
            return (
            <div key={index} className={`flex gap-4 items-center`}>
              <div>
                EM {index + 1}: {points.em[index]?.x.toFixed(2)}, {points.em[index]?.y.toFixed(2)}
              </div>
              <div>
                MIMS {index + 1}: {points.mims[index]?.x.toFixed(2)}, {points.mims[index]?.y.toFixed(2)}
              </div>
              <XCircleIcon onClick={() => {
                canvasStore.removePoint(index);
                mimsStore.removePoint(index);
              }} className="cursor-pointer" />
            </div>
          )})}
          {(points.em?.length === 3 && points.mims?.length === 3) ? (
            <button onClick={submitImageSetPoints}>Submit points</button>
          ) : null}
        </div>
        ) : null}
    </div>
    </div>
  );
};
export default MimsImageSetDetail;
