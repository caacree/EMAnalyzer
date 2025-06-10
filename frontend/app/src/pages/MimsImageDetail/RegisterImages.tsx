/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/shared/ui/tabs";
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";
import OpenSeaDragonSegmenter from "@/components/shared/OpenSeaDragonSegmenter";
import { usePrepareCanvasForGuiQuery } from "@/queries/queries";
import { cn } from "@/lib/utils";
import DetailAligned from "./DetailAligned";

const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_image/${id}/`);
  return res.data;
};

const fetchExistingRegistration = async (id: string) => {
  const res = await api.get(`mims_image/${id}/existing_registration_data/`);
  return res.data;
};

const MimsImage = () => {
  const canvasStore = useCanvasViewer();
  const mimsStore = useMimsViewer();
  const { setCoordinates: setEmCoordinates } = canvasStore;
  const { setFlip: setMimsFlip, setRotation: setMimsRotation } = mimsStore;
  const [openseadragonOptions, setOpenseadragonOptions] = useState<any>({defaultZoomLevel: 1});
  const [selectedIsotope, setSelectedIsotope] = useState("32S");
  const [isRegistering, setIsRegistering] = useState(false);

  const queryClient = useQueryClient();
  const navigate = useNavigate({ from: window.location.pathname });
  const { mimsImageId } = useParams({ strict: false });

  const { data: existingRegistrationData } = useQuery({
    queryKey: ['existing_registration', mimsImageId],
    queryFn: () => fetchExistingRegistration(mimsImageId as string)
  });
  useEffect(() => {
    if (existingRegistrationData) {
      existingRegistrationData.em_shapes.forEach((shape: any) => {
        canvasStore.addOverlay({
          type: "shape_confirmed",
          data: { polygon: shape },
          color: "green"
        });
      });
      existingRegistrationData.mims_shapes.forEach((shape: any) => {
        mimsStore.addOverlay({
          type: "shape_confirmed",
          data: { polygon: shape },
          color: "green"
        });
      });
    }
  }, [existingRegistrationData]);

  const { data: mimsImage } = useQuery({
    queryKey: ['mims_image', mimsImageId], 
    queryFn: () => fetchMimsImageDetail(mimsImageId as string)
  });
  usePrepareCanvasForGuiQuery(mimsImage?.image_set?.canvas.id);
  
  useEffect(() => {
    if (mimsImage?.canvas_bbox?.length) {
      const defaultZoomLevel = mimsImage?.pixel_size_nm / mimsImage?.image_set?.canvas.pixel_size_nm
      if (openseadragonOptions.defaultZoomLevel !== defaultZoomLevel && mimsImage?.pixel_size_nm && defaultZoomLevel < 10000) {
        setOpenseadragonOptions({defaultZoomLevel});
      }
      const min_x = Math.min(...mimsImage.canvas_bbox.map((p: any) => p[0]));
      const min_y = Math.min(...mimsImage.canvas_bbox.map((p: any) => p[1]));
      const max_x = Math.max(...mimsImage.canvas_bbox.map((p: any) => p[0]));
      const max_y = Math.max(...mimsImage.canvas_bbox.map((p: any) => p[1]));
      const em_bbox = [{x:min_x, y:min_y, id: "em_tl"}, {x:max_x, y:max_y, id: "em_br"}];
      setEmCoordinates(em_bbox);
      setMimsFlip(mimsImage?.image_set?.flip);
      setMimsRotation(mimsImage?.image_set?.flip ? mimsImage?.image_set?.rotation_degrees : 360 - mimsImage?.image_set?.rotation_degrees);
      setSelectedIsotope(mimsImage?.isotopes[0]?.name);
    }
  }, [mimsImage]);
  
  const handleOutsideCanvas = () => {
    api.post(`mims_image/${mimsImageId}/outside_canvas/`).then(() => {
      queryClient.invalidateQueries();
      navigate({ to: `/canvas/${mimsImage?.image_set?.canvas.id}` });
    })
  }
  const handleReset = () => {
    api.post(`mims_image/${mimsImageId}/reset/`).then(() => {
      queryClient.invalidateQueries();
    })
  }

  const handleSubmit = () => {
    const data = {
      em_shapes: canvasStore.overlays.filter(p => p.data?.polygon?.length > 3).map((o: any) => o.data?.polygon.map((p: any) => p.slice(0, 2)).filter((p: any) => p)),
      mims_shapes: mimsStore.overlays.map((o: any) => o.data?.polygon.map((p: any) => p.slice(0, 2)).filter((p: any) => p)),
      em_points: canvasStore.points.filter((p: any) => p.type === "point_confirmed").map((p: any) => ([p.y, p.x])),
      mims_points: mimsStore.points.filter((p: any) => p.type === "point_confirmed").map((p: any) => ([p.y, p.x]))
    };
    api.post(`mims_image/${mimsImageId}/register/`, data).then(() => {
      queryClient.invalidateQueries();
      // navigate({ to: `/canvas/${mimsImage?.image_set?.canvas.id}` });
    })
  }

  const clearAll = () => {
    canvasStore.clearPoints();
    mimsStore.clearPoints();
    canvasStore.clearOverlays();
    mimsStore.clearOverlays();
  }
  
  if (!mimsImage) {
    return <div>Loading...</div>;
  }
  
  if (mimsImage.status === "DEWARPED_ALIGNED" && !isRegistering) {
    return <DetailAligned isRegistering={isRegistering} setIsRegistering={setIsRegistering} />
  }
  
  return (
    <div className="flex flex-col w-full m-4 mb-5">
      <div className="flex gap-8">
        <Link onClick={clearAll} to={`/canvas/${mimsImage?.image_set?.canvas.id}`}>Back to EM Image</Link>
        <div>{mimsImage?.file?.split('/').pop()}</div>
      </div>
      <div className="mt-2 mb-8 flex gap-5 grow">
        <div className="flex grow flex-col">
          <div className="flex gap-4 items-center mb-2">
            <div><button onClick={handleSubmit}>Submit</button></div>
          </div>
          <div className="flex flex-col">
            <div className="w-[600px] h-[600px]">
                <OpenSeaDragonSegmenter 
                  iiifContent={`${mimsImage?.em_dzi}`}
                  canvasStore={canvasStore}
                  isotope="em"
                />
          </div>
          </div>
        </div>
        <div className="flex flex-col grow">
          {mimsImage.status !== "DEWARPED_ALIGNED" && (
            <div className="flex gap-4 items-center mb-2">
            <div><button onClick={handleReset}>Reset</button></div>
            <div><button onClick={handleOutsideCanvas}>Outside Canvas</button></div>
          </div>
          )}
          <div className="flex grow h-full">
            <Tabs value={selectedIsotope} className="flex flex-col grow">
              <TabsList className="flex space-x-1">
                {mimsImage?.isotopes?.map((isotope: any) => (
                  <TabsTrigger key={isotope.name} value={isotope.name} onClick={() => setSelectedIsotope(isotope.name)}>
                    {isotope.name}
                  </TabsTrigger>
                ))}
              </TabsList>
            {mimsImage?.isotopes?.map((isotope: any) => {
              const isAu = isotope.name == "197Au";
              let url = `http://localhost:8000/api/mims_image/${mimsImage.id}/image.png?species=${isotope.name}`
              if (isAu) {
                url += "&binarize=true"
              } else {
                url += "&autocontrast=true"
              }
              const isActive = selectedIsotope === isotope.name;
              return (
                <TabsContent key={isotope.name} value={isotope.name}  className={cn("flex flex-col", isActive ? "grow" : "hidden")}>
                  <OpenSeaDragonSegmenter 
                    url={url}
                    canvasStore={mimsStore}
                    isotope={isotope.name}
                  />
                </TabsContent>
            )})}
            </Tabs>
        </div>
        </div>
      </div>
    </div>
  );
};

export default MimsImage;
