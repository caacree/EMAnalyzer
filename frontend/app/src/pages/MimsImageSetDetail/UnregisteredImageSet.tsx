/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/shared/ui/tabs";
import { Checkbox } from "@/components/shared/ui/checkbox";
import { Slider } from "@/components/shared/ui/slider";
import { XCircleIcon } from "lucide-react";
import ControlledOpenSeaDragon from '@/components/shared/ControlledOpenSeaDragon';
import { API_BASE_URL, buildMediaURL } from "@/api/api";
import { cn } from "@/lib/utils";

interface UnregisteredImageSetProps {
  selectedMimsSet: any;
  image: any;
  selectedIsotope: string;
  setSelectedIsotope: (isotope: string) => void;
  mode: "shapes" | "draw" | "navigate" | "points";
  setMode: (mode: "shapes" | "draw" | "navigate" | "points") => void;
  points: any;
  canvasStoreApi: any;
  mimsStoreApi: any;
  mimsStore: any;
  canvasStore: any;
  setMimsFlip: (flip: boolean) => void;
  setMimsRotation: (rotation: number) => void;
  submitImageSetPoints: () => void;
}

// Component for non-registered MIMS Image Sets - shows original point selection view
const UnregisteredImageSet: React.FC<UnregisteredImageSetProps> = ({
  selectedMimsSet,
  image,
  selectedIsotope,
  setSelectedIsotope,
  mode,
  setMode,
  points,
  canvasStoreApi,
  mimsStoreApi,
  mimsStore,
  canvasStore,
  setMimsFlip,
  setMimsRotation,
  submitImageSetPoints
}) => {
  console.log(selectedMimsSet?.mims_overlays);
  return (
    <>
      <div className="flex w-full grow">
        <div className="flex w-1/2 max-w-1/2 min-h-[400px] grow">
          <ControlledOpenSeaDragon 
            iiifContent={buildMediaURL(image.dzi_file)} 
            canvasStore={canvasStoreApi}
            mode={mode}
          />
        </div>
        <div className="flex w-1/2 max-w-1/2">
          <div className={cn("flex flex-col grow gap-3 max-w-full overflow-hidden min-h-[400px]")}>
            {selectedMimsSet ? (
              <Tabs value={selectedIsotope} className="flex flex-col grow">
                <TabsList className="flex space-x-1">
                  {selectedMimsSet?.mims_overlays?.map((overlay: any) => (
                    <TabsTrigger key={overlay.isotope} value={overlay.isotope} onClick={() => setSelectedIsotope(overlay.isotope)}>
                      {overlay.isotope}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {selectedMimsSet?.mims_overlays?.map((overlay: any) => {
                  const isActive = selectedIsotope === overlay.isotope;
                  let iiifContent, url = undefined;
                  if (selectedMimsSet.mims_images.length > 1) {
                    if (overlay.dzi_url.endsWith(".tif")) {
                      url = buildMediaURL(overlay.dzi_url)
                    } else {
                      iiifContent = buildMediaURL(overlay.dzi_url+"/info.json")
                    }
                  } else {
                    url = `${API_BASE_URL}mims_image/${selectedMimsSet.mims_images[0].id}/image.png?species=${overlay.isotope}&autocontrast=true`
                  }
                  return (
                  <TabsContent key={overlay.isotope} value={overlay.isotope} className={cn("flex flex-col", isActive ? "grow" : "hidden")}>
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
                        canvasStore={mimsStoreApi}
                        mode={mode}
                      />
                    </div>
                  </TabsContent>
                )})}
              </Tabs>
            ) : null}
          </div>
        </div>
      </div>
      {selectedMimsSet ? (
        <div className="flex flex-col">
          <div className="flex gap-2 items-center">
            <div>Select points</div>
            <Checkbox checked={mode === "points"} onCheckedChange={() => mode === "points" ? setMode("navigate") : setMode("points")} />
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
                if (points.em[index]) {
                  canvasStore.removePoint(points.em[index].id);
                }
                if (points.mims[index]) {
                  mimsStore.removePoint(points.mims[index].id);
                }
              }} className="cursor-pointer" />
            </div>
          )})}
          {(points.em?.length === 3 && points.mims?.length === 3) ? (
            <button onClick={submitImageSetPoints}>Submit points</button>
          ) : null}
        </div>
      ) : null}
    </>
  );
};

export default UnregisteredImageSet;