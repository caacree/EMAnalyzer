/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/shared/ui/tabs";
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";
import { cn } from "@/lib/utils";
import ControlledOpenSeaDragon from "@/components/shared/ControlledOpenSeaDragon";
import { Slider } from "@/components/shared/ui/slider";
import { Checkbox } from "../../components/shared/ui/checkbox";
import { TrashIcon } from "lucide-react";
import RegistrationPage from "./RegistrationPage";

const updateAlignmentStatus = async (
  mimsImageId: string, savedEmPos: any, rotation: number, flip: boolean
) => {
  const post = {
    zoom: savedEmPos?.zoom, 
    xOffset: savedEmPos?.xOffset, 
    yOffset: savedEmPos?.yOffset, 
    rotation, 
    flip
  };
  return api.post(`mims_image/${mimsImageId}/set_alignment/`, post).then(() => {
    history.back();
  });
}
const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_image/${id}/`);
  return res.data;
};

const MimsImage = () => {
  const canvasStore = useCanvasViewer();
  const mimsStore = useMimsViewer();
  const { setZoom: setEmZoom, setFlip: setEmFlip, setRotation: setEmRotation } = canvasStore;
  const { setZoom: setMimsZoom, setFlip: setMimsFlip, setRotation: setMimsRotation } = mimsStore;
  const [openseadragonOptions, setOpenseadragonOptions] = useState<any>({defaultZoomLevel: 1});
  const [savedEmPos, setSavedEmPos] = useState<any | null>(null);
  const [selectedAlignment, setSelectedAlignment] = useState<string>('');
  const [selectedIsotope, setSelectedIsotope] = useState("32S");
  const [selectedEmPoints, setSelectedEmPoints] = useState<any | null>([]);
  const [selectedMimsPoints, setSelectedMimsPoints] = useState<any | null>([]);
  const [highlightedPointIndex, setHighlightedPointIndex] = useState<number | null>(null);


  const queryClient = useQueryClient();
  const navigate = useNavigate({ from: window.location.pathname });
  const { mimsImageId } = useParams({ strict: false });
  const { data: mimsImage, isLoading } = useQuery({
    queryKey: ['mims_image', mimsImageId], 
    queryFn: () => fetchMimsImageDetail(mimsImageId as string)
  });
  

  const selectAlignment = (alignmentId: string) => {
    setSelectedAlignment(alignmentId);

    const alignment = mimsImage?.alignments?.find((al: any) => al.id == alignmentId)
    if (alignment) {
      setEmRotation(alignment?.rotation_degrees);
      setEmFlip(alignment?.flip_hor);
      setEmZoom(1/alignment?.scale);
      setMimsRotation(alignment?.rotation_degrees);
      setMimsFlip(alignment?.flip_hor);
      setMimsZoom(1/alignment?.scale);
      setSavedEmPos({
        zoom: 1/alignment?.scale,
        xOffset: alignment?.x_offset,
        yOffset: alignment?.y_offset,
      });
    }
  }
  useEffect(() => {
    if (mimsImage?.alignments?.length) {
      selectAlignment(mimsImage?.alignments[0].id);
    }
    const defaultZoomLevel = mimsImage?.pixel_size_nm / mimsImage?.image_set?.canvas.pixel_size_nm
    if (openseadragonOptions.defaultZoomLevel !== defaultZoomLevel && mimsImage?.pixel_size_nm && defaultZoomLevel < 10000) {
      setOpenseadragonOptions({defaultZoomLevel});
    }
  }, [mimsImage]);

  if (isLoading) {
    return <p>Loading...</p>;
  }
  const totalPoints = Math.max(selectedEmPoints.length, selectedMimsPoints.length);
  const updateSelectedEmPoints = (pos: any) => {
    setSelectedEmPoints((prevPoints: any[]) => [...prevPoints, pos]);
  };
  
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
  
  if (["AWAITING_REGISTRATION", "REGISTERING", "DEWARP PENDING"].indexOf(mimsImage?.status) !== -1 && mimsImage?.alignments?.length) {
    return <RegistrationPage />;
  }
  return (
    <div className="flex flex-col w-full m-4">
      <div className="flex gap-8">
        <Link to={`/canvas/${mimsImage?.image_set?.canvas.id}`}>Back to EM Image</Link>
        <div>{mimsImage?.file?.split('/').pop()}</div>
      </div>
      <div className="mt-2 flex gap-5 grow">
        <div className="flex grow flex-col">
          <div className="flex gap-4 items-center mb-2">Suggested Alignments: 
            <Tabs defaultValue={selectedAlignment}>
              <TabsList className="flex space-x-1">
                {mimsImage?.alignments?.map((alignment: any, alignmentIndex: number) => (
                  <TabsTrigger key={alignment.id} value={alignment.id} onClick={() => selectAlignment(alignment.id)}>
                    {alignmentIndex}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <div><button onClick={handleReset}>Reset</button></div>
            <button onClick={() => updateAlignmentStatus(
                mimsImage?.id, savedEmPos, useCanvasViewer.getState().rotation, useCanvasViewer.getState().flip
              )}
            >Correct</button>

          <div><button onClick={handleOutsideCanvas}>Outside Canvas</button></div>
          </div>
          <div>{mimsImage?.alignments?.find((al: any) => al.id == selectedAlignment)?.status}</div>
          <div className="flex flex-col">
            <div className="w-[600px] h-[600px]">
              <ControlledOpenSeaDragon 
                iiifContent={`http://localhost:8000/${mimsImage?.em_dzi}`}
                canvasStore={canvasStore}
                allowZoom={true}
                allowFlip={true}
                allowRotation={true}
                allowSelection={true}
              />
          </div>
          </div>
        </div>
        <div className="flex grow">
          <Tabs defaultValue={selectedIsotope}>
            <TabsList className="flex space-x-1">
              {mimsImage.isotopes?.map((isotope: any) => (
                <TabsTrigger key={isotope.name} value={isotope.name} onClick={() => setSelectedIsotope(isotope.name)}>
                  {isotope.name}
                </TabsTrigger>
              ))}
            </TabsList>
          {mimsImage.isotopes?.map((isotope: any) => {
            const options = {
              degrees: Math.round(useCanvasViewer.getState().rotation),
              flipped: useCanvasViewer.getState().flip
            }
            return (
              <TabsContent key={isotope.name} value={isotope.name}>
                <div className="flex items-center justify-between">
                  <div className="flex gap-2 items-center">
                    Flip: <Checkbox checked={useMimsViewer.getState().flip} onCheckedChange={setMimsFlip} />
                  </div>
                  <div className="flex gap-2 items-center">
                    Rotation:<Slider value={[useMimsViewer.getState().rotation]} min={0} max={360} onValueChange={(v) => setMimsRotation(v?.[0])} />{useMimsViewer.getState().rotation}&deg;
                  </div>
                </div>
                <ControlledOpenSeaDragon 
                  iiifContent={isotope.url}
                  canvasStore={mimsStore}
                  allowZoom={true}
                  allowFlip={true}
                  allowRotation={true}
                  allowSelection={true}
                />
              </TabsContent>
          )})}
          </Tabs>
        </div>
      </div>
      <div className="flex flex-col">
        <div>Selected points</div>
        {[...Array(totalPoints).keys()].map((_, index) => (
          <div key={index} className={cn("flex gap-4 items-center", index === highlightedPointIndex && "bg-gray-200")}>
            <div onClick={() => setHighlightedPointIndex(index)} style={{ fontWeight: index === highlightedPointIndex ? 'bold' : 'normal' }}>
              EM: {selectedEmPoints[index]?.x.toFixed(2)}, {selectedEmPoints[index]?.y.toFixed(2)}
            </div>
            <div onClick={() => setHighlightedPointIndex(index)} style={{ fontWeight: index === highlightedPointIndex ? 'bold' : 'normal' }}>
              MIMS: {selectedMimsPoints[index]?.x.toFixed(2)}, {selectedMimsPoints[index]?.y.toFixed(2)}
            </div>
            <TrashIcon onClick={() => {
              setSelectedEmPoints((prev: any) => prev.filter((_: any, i: any) => i !== index));
              setSelectedMimsPoints((prev: any) => prev.filter((_: any, i: any) => i !== index));
            }} className="cursor-pointer" />
          </div>
        ))}
      </div>
    </div>
  );
};

export default MimsImage;
