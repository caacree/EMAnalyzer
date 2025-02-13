/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link,  useNavigate, useParams, useSearch } from "@tanstack/react-router";
import React, { useEffect,  useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/api";
import ControlledOpenSeaDragon from '@/components/shared/ControlledOpenSeaDragon';
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";
import MIMSImageSet from "./MimsImageSetListItem";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/shared/ui/tabs";
import { Checkbox } from "@/components/shared/ui/checkbox";
import { Slider } from "@/components/shared/ui/slider";
import { XCircleIcon } from "lucide-react";
import { postImageSetPoints } from "@/api/api";
import { cn } from "@/lib/utils";
import { usePrepareCanvasForGuiQuery } from "@/queries/queries";

const fetchCanvasDetail = async (id: string) => {
  const res = await api.get(`canvas/${id}/`);
  return res.data;
};

const MimsImageSetDetail = () => {
  const params = useParams({ strict: false });
  const searchParams = useSearch({ strict: false });
  const queryClient = useQueryClient();
  const { canvasId } = params;
  const { mimsImageSet } = searchParams as any;
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
  const [files, setFiles] = useState<File[]>([]);
  const points = {em: canvasStore.points, mims: mimsStore.points};

  const image = canvas?.images?.[0];
  usePrepareCanvasForGuiQuery(canvasId as string);

  useEffect(() => {
    if (image && mimsImageSet) {
      const selectedMimsSet = canvas?.mims_sets?.find((imageSet: any) => imageSet.id === mimsImageSet);
      if (!selectedMimsSet) {
        return;
      }
      const degrees = (selectedMimsSet?.rotation_degrees) % 360
      setMimsFlip(selectedMimsSet?.flip);
      setMimsRotation(degrees);
      setSelectedIsotope(Object.keys(selectedMimsSet?.composite_images)[0]);
    }
  }, [canvas, mimsImageSet]);
    
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setFiles(Array.from(event.target.files));
    }
  };

  const handleSubmit = async () => {
    const formData = new FormData();
    
    // Add the EM image ID to the form data
    formData.append('canvas', canvas.id);
  
    // Add files to the form data
    files.forEach((file, index) => {
      formData.append(`file_${index}`, file);
    });
  
    try {
      await api.post('/mims_image_set/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }).then(() => queryClient.invalidateQueries());
    } catch (error) {
      alert('Failed to upload files');
    }
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
  return (
    <div className="w-full flex flex-col ml-10 gap-5 max-h-[80%]">
      <div className="flex gap-20">
        <Link to={`/canvas/${canvas.id}`}>
          <h2 className="flex gap-20">Canvas: {canvas.name}</h2>
        </Link>
        <div>{selectedMimsSet ? `Selected Mims Image Set: ${selectedMimsSet.id}` : null}</div>
      </div>
      <div className="flex w-full">
        <div className="flex w-1/2">
          <ControlledOpenSeaDragon 
            iiifContent={image.dzi_file} 
            canvasStore={canvasStore}
            allowZoom={true}
            allowFlip={false}
            allowRotation={false}
            allowPointSelection={isSelectingPoints}
          />
        </div>
        <div className="flex w-1/2">
          <div className={cn("flex flex-col gap-3", !mimsImageSet && "max-h-[600px] overflow-scroll")}>
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
            {selectedMimsSet?.composite_images ? (
              <div className="">
                <Tabs defaultValue={selectedIsotope}>
                  <TabsList className="flex space-x-1">
                    {Object.keys(selectedMimsSet.composite_images).map((isotope: any) => (
                      <TabsTrigger key={isotope} value={isotope} onClick={() => setSelectedIsotope(isotope)}>
                        {isotope}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  {Object.keys(selectedMimsSet.composite_images).map((isotope: any) => {
                    return (
                    <TabsContent key={isotope} value={isotope}>
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
                      <ControlledOpenSeaDragon 
                        iiifContent={"http://localhost:8000" + selectedMimsSet.composite_images[isotope]+"/info.json"}
                        canvasStore={mimsStore}
                        allowZoom={true}
                        allowFlip={true}
                        allowRotation={true}
                        allowPointSelection={isSelectingPoints}
                      />
                    </TabsContent>
                  )})}
                </Tabs>
              </div>
            ) : null}
            <label htmlFor="file-input">Add new MIMS image set:</label>
            <input
              type="file"
              id="file-input"
              multiple
              onChange={handleFileChange}
              className="mb-2"
            />
            <button
              onClick={handleSubmit}
              className="bg-blue-500 text-white px-4 py-2 rounded"
            >
              Submit
            </button>
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
  );
};
export default MimsImageSetDetail;
