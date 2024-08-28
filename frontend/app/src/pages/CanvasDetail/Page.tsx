/* eslint-disable @typescript-eslint/no-explicit-any */
import { Route, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import React, { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/api";
import OpenSeaDragon from '@/components/shared/OpenSeaDragon';
import MIMSImageSet from "./MimsImageSetListItem";
import MimsOpenSeaDragon from "../../components/shared/MimsOpenSeaDragon";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/shared/ui/tabs";
import { Checkbox } from "../../components/shared/ui/checkbox";
import { Slider } from "../../components/shared/ui/slider";
import { TrashIcon, XCircleIcon } from "lucide-react";
import { postImageSetPoints } from "../../api/api";

const fetchCanvasDetail = async (id: string) => {
  const res = await api.get(`canvas/${id}/`);
  return res.data;
};

const CanvasDetail = () => {
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
  const [mimsOptions, setMimsOptions] = useState<any>({'flipped': false, 'degrees': 0});
  const [isSelectingPoints, setIsSelectingPoints] = useState(false);
  const [points, setPoints] = useState<any>({ em: [], mims: [] });
  const handleEMClickRef = useRef((point: any) => {});
  const handleMimsClickRef = useRef((point: any) => {});
  const [files, setFiles] = useState<File[]>([]);
  useEffect(() => {
    handleEMClickRef.current = (point: any) => {
      if (isSelectingPoints && point && points?.em.length < 3) {
        setPoints({ ...points, em: [...points.em, point] });
      }
    };
    handleMimsClickRef.current = (point: any) => {
      if (isSelectingPoints && point && points?.mims.length < 3) {
        setPoints({ ...points, mims: [...points.mims, point] });
      }
    }
  }, [isSelectingPoints, points]);

  const image = canvas?.images?.[0];

  useEffect(() => {
    if (image && mimsImageSet) {
      const selectedMimsSet = canvas?.mims_sets?.find((imageSet: any) => imageSet.id === mimsImageSet);
      if (!selectedMimsSet) {
        return;
      }
      const degrees = (selectedMimsSet?.rotation_degrees) % 360
      setMimsOptions({flipped: selectedMimsSet?.flip, degrees});
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
    postImageSetPoints(mimsImageSet, points)
  }

  const handleDeleteMimsSet = (imageSetId: string) => {
    api.delete(`/mims_image_set/${imageSetId}/`).then(() => queryClient.invalidateQueries());
  }

  const selectedMimsSet = canvas?.mims_sets?.find((imageSet: any) => imageSet.id === mimsImageSet);
  return (
    <div className="w-full flex flex-col ml-10 gap-5">
      <h2 className="flex gap-20"><span>Canvas: {canvas.name}</span><span>{selectedMimsSet ? `Selected Mims Image Set: ${selectedMimsSet.id}` : null}</span></h2>
      {selectedMimsSet ? (
        <div>
          <div className="flex gap-2 items-center">
            <div>Select points</div>
            <Checkbox checked={isSelectingPoints} onCheckedChange={setIsSelectingPoints} />
          </div>
          <div className="flex flex-col">
            <div>Selected Points</div>
            {[0,1,2].map((point, index) => {
              if (!points.em[index] && !points.mims[index]) {
                return null;
              }
              return (
              <div key={point} className={`flex gap-4 items-center`}>
                <div>
                  EM {index + 1}: {points.em[index]?.x.toFixed(2)}, {points.em[index]?.y.toFixed(2)}
                </div>
                <div>
                  MIMS {index + 1}: {points.mims[index]?.x.toFixed(2)}, {points.mims[index]?.y.toFixed(2)}
                </div>
                <XCircleIcon onClick={() => {
                  setPoints(prev => ({
                    em: prev.em.filter((_, i) => i !== index),
                    mims: prev.mims.filter((_, i) => i !== index)
                  }));
                }} className="cursor-pointer" />
              </div>
            )})}
            {(points.em?.length === 3 && points.mims?.length === 3) ? (
              <button onClick={submitImageSetPoints}>Submit points</button>
            ) : null}
          </div>
        </div>
      ) : null}
      <div className="flex w-full">
        <div className="flex w-1/2">
          <OpenSeaDragon iiifContent={image.dzi_file} onClick={(point: any) => handleEMClickRef.current(point)} points={points.em} />
        </div>
        <div className="flex w-1/2">
          <div className="flex flex-col gap-3">
            {!mimsImageSet ? (
              <>
                <div>MIMS Image sets</div>
                {canvas?.mims_sets?.map((mimsImageSet: any) => (
                  <><MIMSImageSet key={mimsImageSet.id} mimsImageSet={mimsImageSet} onSelect={(newId: string) => {
                    navigate({ search: (prev: any) => ({ ...prev, mimsImageSet: newId }) });
                  }} /><button onClick={() => handleDeleteMimsSet(mimsImageSet.id)}>
                  <TrashIcon />
                </button></>
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
                  {Object.keys(selectedMimsSet.composite_images).map((isotope: any) => (
                    <TabsContent key={isotope} value={isotope}>
                      <div className="flex items-center justify-between">
                        <div className="flex gap-2 items-center">
                          Flip: <Checkbox checked={mimsOptions.flipped} onCheckedChange={(checked: boolean) => setMimsOptions({flipped: checked, degrees: mimsOptions.degrees})} />
                        </div>
                        <div className="flex gap-2 items-center">
                          Rotation:<Slider value={[mimsOptions.degrees]} min={0} max={360} onValueChange={(val) => setMimsOptions({flipped: mimsOptions.flipped, degrees: Math.round(val)})} />{mimsOptions.degrees}&deg;
                        </div>
                      </div>
                      <MimsOpenSeaDragon 
                        iiifContent={"http://localhost:8000" + selectedMimsSet.composite_images[isotope]+"/info.json"} 
                        options={mimsOptions}
                        onClick={(point: any) => handleMimsClickRef.current(point)}
                        points={points.mims}
                        allowZoom
                      />
                    </TabsContent>
                  ))}
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
    </div>
  );
};
export default CanvasDetail;