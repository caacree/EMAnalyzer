/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/shared/ui/tabs";
import OpenSeaDragon from "@/components/shared/OpenSeaDragon";
import { cn } from "@/lib/utils";
import MimsOpenSeaDragon from "@/components/shared/MimsOpenSeaDragon";
import { Slider } from "@/components/shared/ui/slider";
import { Checkbox } from "../../components/shared/ui/checkbox";
import { TrashIcon } from "lucide-react";

const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_images/${id}/`);
  return res.data;
};

const MimsImage = () => {
  const [openseadragonOptions, setOpenseadragonOptions] = useState<any>({defaultZoomLevel: 1});
  const [openseadragonEmViewerPos, setOpenseadragonEmViewerPos] = useState<any>({});
  const [rotationSliderValue, setRotationSliderValue] = useState(0);
  const [mimsflip_hor, setMimsflip_hor] = useState(false);
  const [selectedAlignment, setSelectedAlignment] = useState(0);
  const [selectedIsotope, setSelectedIsotope] = useState(0);
  const [selectedEmPoints, setSelectedEmPoints] = useState<any | null>([]);
  const [selectedMimsPoints, setSelectedMimsPoints] = useState<any | null>([]);
  const [highlightedPointIndex, setHighlightedPointIndex] = useState<number | null>(null);
  const [isSelectingPoints, setIsSelectingPoints] = useState<boolean>(false);

  const { mimsImageId } = useParams({ strict: false });
  const { data: mimsImage, isLoading } = useQuery({
    queryKey: ['mims_image', mimsImageId], 
    queryFn: () => fetchMimsImageDetail(mimsImageId as string)
  });

  const selectAlignment = (alignmentIndex: number) => {
    setSelectedAlignment(alignmentIndex);
    setRotationSliderValue(alignment.rotation_degrees);
    setMimsflip_hor(alignment.flip_hor)
    setOpenseadragonEmViewerPos({
      zoom: alignment.scale,
      xOffset: alignment.x_offset,
      yOffset: alignment.y_offset,
    });
  }
  useEffect(() => {
    if (mimsImage?.alignments.length) {
      selectAlignment(0);
    }
    const defaultZoomLevel = mimsImage?.pixel_size_nm / mimsImage?.image_set.em_image.pixel_size_nm
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
  const emPos = {
    zoom: 0.070629169167,
  }
  return (
    <div className="flex flex-col w-full m-4">
      <div className="flex gap-8">
        <Link to={`/em_image/${mimsImage.image_set.em_image.id}`}>Back to EM Image</Link>
        <div>{mimsImage.file.split('/').pop()}</div>
      </div>
      <div className="mt-2 flex gap-5 grow">
        <div className="flex grow flex-col">
          <div className="flex gap-4 items-center mb-2">Suggested Alignments: 
            <Tabs defaultValue={selectedAlignment}>
              <TabsList className="flex space-x-1">
                {mimsImage.alignments?.map((alignment: any, alignmentIndex: number) => (
                  <TabsTrigger key={alignmentIndex} value={alignmentIndex} onClick={() => selectAlignment(alignmentIndex)}>
                    {alignmentIndex}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
          <div className="w-[600px] h-[700px]">
            <OpenSeaDragon 
              iiifContent={mimsImage.image_set.em_image.dzi_file} 
              options={openseadragonOptions} 
              viewerPos={emPos}
              onClick={updateSelectedEmPoints}
            />
          </div>
        </div>
        <div className="flex grow">
          <Tabs defaultValue={selectedIsotope}>
            <TabsList className="flex space-x-1">
              {mimsImage.isotopes?.map((isotope: any, isotopeIndex: number) => (
                <TabsTrigger key={isotopeIndex} value={isotopeIndex} onClick={() => setSelectedIsotope(isotopeIndex)}>
                  {isotope.name}
                </TabsTrigger>
              ))}
            </TabsList>
          {mimsImage.isotopes?.map((isotope: any, isotopeIndex: number) => (
            <TabsContent key={isotopeIndex} value={isotopeIndex}>
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
                options={{
                  degrees: Math.round(rotationSliderValue),
                  flipped: mimsflip_hor
                }}
                onClick={(pos: any) => setSelectedMimsPoints([...selectedMimsPoints, pos])}
              />
            </TabsContent>
          ))}
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
