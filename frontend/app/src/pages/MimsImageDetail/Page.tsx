/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "@/api/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/shared/ui/tabs";
import OpenSeaDragon from "@/components/shared/OpenSeaDragon";
import { cn } from "@/lib/utils";
import MimsOpenSeaDragon from "@/components/shared/MimsOpenSeaDragon";
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
  return api.post(`mims_image/${mimsImageId}/set_alignment/`, post);
}
const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_image/${id}/`);
  return res.data;
};

const MimsImage = () => {
  const [openseadragonOptions, setOpenseadragonOptions] = useState<any>({defaultZoomLevel: 1});
  const [openseadragonEmViewerPos, setOpenseadragonEmViewerPos] = useState<any>({});
  const [savedEmPos, setSavedEmPos] = useState<any | null>(null);
  const [rotationSliderValue, setRotationSliderValue] = useState(0);
  const [mimsflip_hor, setMimsflip_hor] = useState(false);
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
      setRotationSliderValue(alignment?.rotation_degrees);
      setMimsflip_hor(alignment?.flip_hor)
      setOpenseadragonEmViewerPos({
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
  
  const handleNoCells = () => {
    api.post(`mims_image/${mimsImageId}/no_cells/`).then(() => {
      queryClient.invalidateQueries();
      navigate({ to: `/canvas/${mimsImage?.image_set?.canvas.id}` });
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
            <button onClick={() => updateAlignmentStatus(
                mimsImage?.id, savedEmPos, rotationSliderValue, mimsflip_hor
              ).then(() => history.back())}
            >Correct</button>

            <div><button onClick={handleNoCells}>No cells</button></div>
          </div>
          <div>{mimsImage?.alignments?.find((al: any) => al.id == selectedAlignment)?.status}</div>
          <div className="flex flex-col">
            <div className="w-[600px] h-[600px]">
              <OpenSeaDragon 
                iiifContent={`http://localhost:8000/${mimsImage?.em_dzi}`}
                options={openseadragonOptions}
                viewerPos={openseadragonEmViewerPos}
                onClick={updateSelectedEmPoints}
                setSavedEmPos={setSavedEmPos}
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
              degrees: Math.round(rotationSliderValue),
              flipped: mimsflip_hor
            }
            return (
              <TabsContent key={isotope.name} value={isotope.name}>
                <div className="flex items-center justify-between">
                  <div className="flex gap-2 items-center">
                    Flip: <Checkbox checked={mimsflip_hor} onCheckedChange={(checked: boolean) => setMimsflip_hor(checked)} />
                  </div>
                  <div className="flex gap-2 items-center">
                    Rotation:<Slider value={[rotationSliderValue]} min={0} max={360} onValueChange={setRotationSliderValue} />{rotationSliderValue}&deg;
                  </div>
                </div>
                <MimsOpenSeaDragon 
                  url={isotope.url} 
                  options={options}
                  // onClick={(pos: any) => setSelectedMimsPoints([...selectedMimsPoints, pos])}
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
