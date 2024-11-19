/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/shared/ui/tabs";
import OpenSeaDragonSegmenter from "@/components/shared/OpenSeaDragonSegmenter";

const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_image/${id}/`);
  return res.data;
};

const MimsImageRegistration = () => {
  const [emShapes, setEmShapes] = useState<any[]>([]);
  const [mimsShapes, setMimsShapes] = useState<any[]>([]);
  const [selectedIsotope, setSelectedIsotope] = useState("32S");

  const queryClient = useQueryClient();

  const { mimsImageId } = useParams({ strict: false });
  const { data: mimsImage } = useQuery({
    queryKey: ['mims_image', mimsImageId], 
    queryFn: () => fetchMimsImageDetail(mimsImageId as string)
  });
  const onEmShapeSelect = (pos: any) => {
    setEmShapes([...emShapes, pos]);
  }
  const onMimsShapeSelect = (pos: any) => {
    setMimsShapes([...mimsShapes, pos]);
  }

  const handleSubmit = () => {
    const data = {
      em_shapes: emShapes,
      mims_shapes: mimsShapes
    };
    api.post(`mims_image/${mimsImageId}/register/`, data).then(() => {
      queryClient.invalidateQueries();
      navigate({ to: `/canvas/${mimsImage?.image_set?.canvas.id}` });
    })
  }
  const handleReset = () => {
    api.post(`mims_image/${mimsImageId}/reset/`).then(() => {
      queryClient.invalidateQueries();
    })
  }
  const navigate = useNavigate({ from: window.location.pathname });
  const handleOutsideCanvas = () => {
    api.post(`mims_image/${mimsImageId}/outside_canvas/`).then(() => {
      queryClient.invalidateQueries();
      navigate({ to: `/canvas/${mimsImage?.image_set?.canvas.id}` });
    })
  }
  
  return (
    <div className="flex flex-col w-full m-4">
      <div className="flex gap-8">
        <Link to={`/canvas/${mimsImage?.image_set?.canvas.id}`}>Back to EM Image</Link>
        <div>{mimsImage?.file?.split('/').pop()}</div>
        <div><button onClick={handleReset}>Reset</button></div>
        <div><button onClick={handleOutsideCanvas}>Outside Canvas</button></div>
      </div>
      <div className="mt-2 flex gap-5 grow">
        <div className="flex grow flex-col mt-[60px]">
          <div className="flex flex-col">
            <div className="w-[600px] h-[600px]">
              <OpenSeaDragonSegmenter
                urls={mimsImage?.registration}
                isotope="em"
                onShapeSelect={onEmShapeSelect}
                shapes={emShapes}
              />
            </div>
          </div>
        </div>
        <div className="flex grow">
          <Tabs defaultValue={selectedIsotope}>
            <TabsList className="flex space-x-1 h-[60px]">
              {mimsImage.isotopes?.map((isotope: any) => (
                <TabsTrigger key={isotope.name} value={isotope.name} onClick={() => setSelectedIsotope(isotope.name)}>
                  {isotope.name}
                </TabsTrigger>
              ))}
            </TabsList>
          {mimsImage.isotopes?.map((isotope: any) => {
            return (
              <TabsContent key={isotope.name} value={isotope.name} className="mt-0">
                <OpenSeaDragonSegmenter
                  urls={mimsImage?.registration}
                  isotope={isotope.name}
                  shapes={mimsShapes}
                  onShapeSelect={onMimsShapeSelect}
                />
              </TabsContent>
          )})}
          </Tabs>
        </div>
      </div>
      <div className="my-4 flex "><button className="grow" onClick={handleSubmit}>Submit</button></div>
    </div>
  );
};

export default MimsImageRegistration;
