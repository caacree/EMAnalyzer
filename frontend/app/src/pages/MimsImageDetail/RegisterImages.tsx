/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate, Link } from "@tanstack/react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/shared/ui/tabs";
import api, { API_BASE_URL, buildMediaURL } from "@/api/api";
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";
import { usePrepareCanvasForGuiQuery } from "@/queries/queries";
import OpenSeaDragonSegmenter from "@/components/shared/OpenSeaDragonSegmenter";
import ShapePointIndexList from "./ShapePointIndexList";
import DetailAligned from "./DetailAligned";
import { v4 as uuidv4 } from 'uuid';

const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_image/${id}/`);
  return res.data;
};

const fetchExistingRegistration = async (id: string) => {
  const res = await api.get(`mims_image/${id}/existing_registration_data/`);
  return res.data;
};

const MimsImage = ({isRegistering, setIsRegistering}: {isRegistering: boolean, setIsRegistering: (isRegistering: boolean) => void}) => {
  const canvasStoreApi = useCanvasViewer;
  const mimsStoreApi = useMimsViewer;
  const canvasStoreState = canvasStoreApi();
  const mimsStoreState = mimsStoreApi();
  const { setCoordinates: setEmCoordinates } = canvasStoreState;
  const { setFlip: setMimsFlip, setRotation: setMimsRotation } = mimsStoreState;

  const [openseadragonOptions, setOpenseadragonOptions] = useState<any>({defaultZoomLevel: 1});
  const [selectedIsotope, setSelectedIsotope] = useState("32S");

  const queryClient = useQueryClient();
  const navigate = useNavigate({ from: window.location.pathname });
  const { mimsImageId } = useParams({ strict: false });

  const { data: existingRegistrationData } = useQuery({
    queryKey: ['existing_registration', mimsImageId],
    queryFn: () => fetchExistingRegistration(mimsImageId as string)
  });
  useEffect(() => {
    if (existingRegistrationData) {
      existingRegistrationData.em_shapes?.forEach((shape: any) => {
        canvasStoreState.addOverlay({
          type: "shape_confirmed",
          data: { polygon: shape },
          color: "green"
        });
      });
      existingRegistrationData.em_points?.forEach(([row, col]: number[]) =>
        canvasStoreState.addPoint({
          id: uuidv4(),
          x: col,
          y: row,
          color: "green",
          type: "point_confirmed",
        })
      );
      existingRegistrationData.mims_shapes?.forEach((shape: any) => {
        mimsStoreState.addOverlay({
          type: "shape_confirmed",
          data: { polygon: shape },
          color: "green"
        });
      });
      existingRegistrationData.mims_points?.forEach(([row, col]: number[]) =>
        mimsStoreState.addPoint({
          id: uuidv4(),
          x: col,
          y: row,
          color: "green",
          type: "point_confirmed",
        })
      );
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
    /*mimsStore.points.forEach((p: any, i: number) => {
      if (i > 34) {
        mimsStore.removePoint(p.id);
      }
    })
    canvasStore.points.forEach((p: any, i: number) => {
      if (i > 34) {
        canvasStore.removePoint(p.id);
      }
    })
    return*/
    const data = {
      em_shapes: canvasStoreState.overlays.filter(p => p.data?.polygon?.length > 3).map((o: any) => o.data?.polygon.map((p: any) => p.slice(0, 2)).filter((p: any) => p)),
      mims_shapes: mimsStoreState.overlays.map((o: any) => o.data?.polygon.map((p: any) => p.slice(0, 2)).filter((p: any) => p)),
      em_points: canvasStoreState.points.filter((p: any) => p.type === "point_confirmed").map((p: any) => ([p.y, p.x])),
      mims_points: mimsStoreState.points.filter((p: any) => p.type === "point_confirmed").map((p: any) => ([p.y, p.x]))
    };
    api.post(`mims_image/${mimsImageId}/register/`, data).then(() => {
      queryClient.invalidateQueries();
      // navigate({ to: `/canvas/${mimsImage?.image_set?.canvas.id}` });
    })
  }

  const clearAll = () => {
    canvasStoreState.clearPoints();
    mimsStoreState.clearPoints();
    canvasStoreState.clearOverlays();
    mimsStoreState.clearOverlays();
  }
  
  if (!mimsImage) {
    return <div>Loading...</div>;
  }
  
  if (mimsImage.status === "DEWARPED_ALIGNED" && !isRegistering) {
    return <DetailAligned isRegistering={isRegistering} setIsRegistering={setIsRegistering} />
  }
  console.log(mimsImage);
  
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
                  iiifContent={buildMediaURL(mimsImage?.em_dzi)}
                  canvasStore={canvasStoreApi}
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
              {/* Only render the active tab content */}
              {mimsImage?.isotopes?.map((isotope: any) => {
                const isAu = isotope.name == "197Au";
                let url = `${API_BASE_URL}mims_image/${mimsImage.id}/image.png?species=${isotope.name}`
                if (isAu) {
                  url += "&binarize=true"
                } else {
                  url += "&autocontrast=true"
                }
                const isActive = selectedIsotope === isotope.name;
                
                // Only render the active tab
                if (!isActive) return null;
                
                return (
                  <TabsContent key={isotope.name} value={isotope.name} className="flex flex-col grow">
                    <OpenSeaDragonSegmenter 
                      url={url}
                      canvasStore={mimsStoreApi}
                      isotope={isotope.name}
                    />
                  </TabsContent>
                );
              })}
            </Tabs>
          </div>
        </div>
      </div>
      <ShapePointIndexList />
    </div>
  );
};

export default MimsImage;
