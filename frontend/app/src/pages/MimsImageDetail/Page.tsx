/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/shared/ui/tabs";
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";
import ControlledOpenSeaDragon from "@/components/shared/ControlledOpenSeaDragon";
import RegistrationPage from "./RegistrationPage";
import OpenSeaDragonSegmenter from "@/components/shared/OpenSeaDragonSegmenter";
import { usePrepareCanvasForGuiQuery } from "@/queries/queries";

const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_image/${id}/`);
  return res.data;
};

const MimsImage = () => {
  const canvasStore = useCanvasViewer();
  const mimsStore = useMimsViewer();
  const { setCoordinates: setEmCoordinates } = canvasStore;
  const { setFlip: setMimsFlip, setRotation: setMimsRotation } = mimsStore;
  const [openseadragonOptions, setOpenseadragonOptions] = useState<any>({defaultZoomLevel: 1});
  const [selectedIsotope, setSelectedIsotope] = useState("32S");
  const [segmentEmShapes, setSegmentEmShapes] = useState<boolean>(true);
  const [readyToSegment, setReadyToSegment] = useState<boolean | string>(false);

  const queryClient = useQueryClient();
  const navigate = useNavigate({ from: window.location.pathname });
  const { mimsImageId } = useParams({ strict: false });

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
      setMimsRotation(mimsImage?.image_set?.rotation_degrees);
      setSelectedIsotope(mimsImage?.isotopes[0]?.name);
    }
    /*api.get(`mims_image/${mimsImageId}/prepare_for_segmentation/`).then(() => {
      const intervalId = setInterval(async () => {
        const response = await api.get(`mims_image/${mimsImageId}/is_segmentation_ready/`);
        if (response.data === true) {
          setReadyToSegment(true);
          clearInterval(intervalId);
        }
      }, 2000);
      return () => clearInterval(intervalId); // Cleanup on component unmount
    });*/
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
      em_shapes: canvasStore.overlays.map((o: any) => o.data?.polygon).filter((p: any) => p),
      mims_shapes: mimsStore.overlays.map((o: any) => o.data?.polygon).filter((p: any) => p)
    };
    api.post(`mims_image/${mimsImageId}/register/`, data).then(() => {
      //queryClient.invalidateQueries();
      //navigate({ to: `/canvas/${mimsImage?.image_set?.canvas.id}` });
    })
  }

  const clearAll = () => {
    canvasStore.clearPoints();
    mimsStore.clearPoints();
    canvasStore.clearOverlays();
    mimsStore.clearOverlays();
  }
  
  if (["AWAITING_REGISTRATION", "REGISTERING", "DEWARP PENDING"].indexOf(mimsImage?.status) !== -1 && mimsImage?.alignments?.length) {
    return <RegistrationPage />;
  }
  if (!mimsImage) {
    return <div>Loading...</div>;
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
            <div><input type="checkbox" checked={segmentEmShapes} onChange={() => setSegmentEmShapes(!segmentEmShapes)} /> Segment EM Shapes</div>
            <div><button onClick={handleSubmit}>Submit</button></div>
          </div>
          <div className="flex flex-col">
            <div className="w-[600px] h-[600px]">
              {segmentEmShapes ? (
                <OpenSeaDragonSegmenter 
                  iiifContent={`http://localhost:8000/${mimsImage?.em_dzi}`}
                  canvasStore={canvasStore}
                  isotope="em"
                />
              ) : (<ControlledOpenSeaDragon 
                iiifContent={`http://localhost:8000/${mimsImage?.em_dzi}`}
                canvasStore={canvasStore}
                allowZoom={true}
                allowFlip={true}
                allowRotation={true}
                allowPointSelection={false}
              />)}
              
          </div>
          </div>
        </div>
        <div className="flex flex-col grow">
          <div className="flex gap-4 items-center mb-2">
            <div><button onClick={handleReset}>Reset</button></div>
            <div><button onClick={handleOutsideCanvas}>Outside Canvas</button></div>
          </div>
          <div className="flex grow">
            <Tabs value={selectedIsotope}>
              <TabsList className="flex space-x-1">
                {mimsImage?.isotopes?.map((isotope: any) => (
                  <TabsTrigger key={isotope.name} value={isotope.name} onClick={() => setSelectedIsotope(isotope.name)}>
                    {isotope.name}
                  </TabsTrigger>
                ))}
              </TabsList>
            {mimsImage?.isotopes?.map((isotope: any) => {
              const url = `http://localhost:8000/api/mims_image/${mimsImage.id}/image.png?species=${isotope.name}&autocontrast=true`
              return (
                <TabsContent key={isotope.name} value={isotope.name}>
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
