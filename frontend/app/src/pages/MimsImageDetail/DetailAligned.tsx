/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import api, { get_mims_image_dewarped_url } from "@/api/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/shared/ui/tabs";
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";
import ControlledOpenSeaDragon from "@/components/shared/ControlledOpenSeaDragon";
import { usePrepareCanvasForGuiQuery } from "@/queries/queries";
import { cn } from "@/lib/utils";
import CreateRatioImage from "./CreateRatioImage";

const fetchMimsImageDetail = async (id: string) => {
  const res = await api.get(`mims_image/${id}/`);
  return res.data;
};

const DetailAligned = ({isRegistering, setIsRegistering}: {isRegistering: boolean, setIsRegistering: (isRegistering: boolean) => void}) => {
  const canvasStore = useCanvasViewer();
  const mimsStore = useMimsViewer();
  const { setCoordinates: setEmCoordinates } = canvasStore;
  const { setFlip: setMimsFlip, setRotation: setMimsRotation } = mimsStore;
  const [openseadragonOptions, setOpenseadragonOptions] = useState<any>({defaultZoomLevel: 1});
  const [selectedIsotope, setSelectedIsotope] = useState("EM");
  const [isDownloading, setIsDownloading] = useState(false);
  const [isRatioDialogOpen, setIsRatioDialogOpen] = useState(false);

  const { mimsImageId } = useParams({ strict: false });

  const { data: mimsImage } = useQuery({
    queryKey: ['mims_image', mimsImageId], 
    queryFn: () => fetchMimsImageDetail(mimsImageId as string)
  });
  usePrepareCanvasForGuiQuery(mimsImage?.image_set?.canvas.id);
  
  useEffect(() => {
    if (mimsImage) {
      const defaultZoomLevel = mimsImage?.pixel_size_nm / mimsImage?.image_set?.canvas.pixel_size_nm
      if (openseadragonOptions.defaultZoomLevel !== defaultZoomLevel && mimsImage?.pixel_size_nm && defaultZoomLevel < 10000) {
        setOpenseadragonOptions({defaultZoomLevel});
      }
      
      setMimsFlip(mimsImage?.image_set?.flip);
      setMimsRotation(mimsImage?.image_set?.flip ? mimsImage?.image_set?.rotation_degrees : 360 - mimsImage?.image_set?.rotation_degrees);
      setSelectedIsotope("EM");
      
      // Set coordinates from registration_bbox of the first mims_tiff_image if available
      if (mimsImage?.mims_tiff_images?.length > 0 && mimsImage.mims_tiff_images[0].registration_bbox) {
        const bbox = mimsImage.mims_tiff_images[0].registration_bbox;
        // Assuming registration_bbox is in the format [[top_left_x, top_left_y], [bottom_right_x, bottom_right_y]]
        const em_bbox = [
          {x: bbox[0][0], y: bbox[0][1], id: "em_tl"}, 
          {x: bbox[1][0], y: bbox[1][1], id: "em_br"}
        ];
        setEmCoordinates(em_bbox);
      }
    }
  }, [mimsImage]);
  
  

  const getDownloadUrl = useCallback(() => {
    if (!mimsImage || selectedIsotope === "EM") return get_mims_image_dewarped_url(mimsImage, {name: "EM", id: "EM"});
    
    // Find the currently selected tiff image
    const selectedTiffImage = mimsImage.mims_tiff_images.find((img: any) => img.name === selectedIsotope);
    
    if (selectedTiffImage) {
      return get_mims_image_dewarped_url(mimsImage, selectedTiffImage);
    }
    
    return "";
  }, [mimsImage, mimsImageId, selectedIsotope]);
  
  // Function to handle download
  const handleDownload = useCallback(async () => {
    try {
      setIsDownloading(true);
      const url = getDownloadUrl();
      if (!url) {
        setIsDownloading(false);
        return;
      }
      
      const response = await fetch(url);
      const blob = await response.blob();
      
      // Create a temporary download link
      const downloadLink = document.createElement('a');
      const filename = `${mimsImage?.name || mimsImage?.file?.split('/').pop().split('.')[0]}_${selectedIsotope}.png`;
      
      // Create a blob URL and set it as the href
      downloadLink.href = URL.createObjectURL(blob);
      downloadLink.download = filename;
      
      // Append to body, click, and remove
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
    } catch (error) {
      console.error("Download failed:", error);
    } finally {
      setIsDownloading(false);
    }
  }, [getDownloadUrl, mimsImage, selectedIsotope]);

  if (!mimsImage) {
    return <div>Loading...</div>;
  }

  return (
    <div className="flex flex-col w-screen max-w-screen m-4 mb-5 relative">
      {isDownloading && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-20 flex items-center justify-center">
          <div className="bg-white p-4 rounded-lg shadow-md flex items-center gap-3">
            <span className="animate-spin h-6 w-6 border-4 border-blue-500 border-t-transparent rounded-full"></span>
            <span className="text-gray-800 font-medium">Downloading image...</span>
          </div>
        </div>
      )}
      <div className="flex justify-between items-center">
        <div className="flex gap-8 items-center">
          <Link to={`/canvas/${mimsImage?.image_set?.canvas.id}`}>Back to EM Image</Link>
          <div>{mimsImage?.file?.split('/').pop()}</div>
        </div>
        <button 
          onClick={handleDownload}
          disabled={isDownloading}
          className={`ml-auto mr-8 px-3 py-1 rounded border border-1 text-black hover:bg-blue-600 flex items-center gap-2 ${isDownloading ? 'opacity-70 cursor-not-allowed' : ''}`}
        >
          {isDownloading ? (
            <>
              <span className="text-black animate-spin h-4 w-4 border border-t-transparent rounded-full"></span>
              <span>Downloading...</span>
            </>
          ) : (
            'Download'
          )}
        </button>
      </div>
      <div className="mt-2 mb-8 flex grow">
        <div className="flex grow">
          <Tabs value={selectedIsotope} className="flex flex-col grow min-h-[600px] justify-center">
            <TabsList className="flex space-x-1">
              <TabsTrigger key="EM" value="EM" onClick={() => setSelectedIsotope("EM")}>
                EM
              </TabsTrigger>
              {mimsImage?.mims_tiff_images?.map((tiffImage: any) => (
                <TabsTrigger key={tiffImage.id} value={tiffImage.name} onClick={() => setSelectedIsotope(tiffImage.name)}>
                  {tiffImage.name}
                </TabsTrigger>
              ))}
              <button 
                onClick={(e) => {
                  e.preventDefault();
                  setIsRatioDialogOpen(true);
                }}
                className="px-3 py-1 rounded border-2 border-green-500 text-green-500 hover:bg-green-500 hover:text-white ml-2"
              >
                Add Ratio Image
              </button>
              <button 
                onClick={(e) => {
                  e.preventDefault();
                  setIsRegistering(!isRegistering);
                }}
                className="px-3 py-1 rounded border-2 border-purple-500 text-purple-500 hover:bg-purple-500 hover:text-white ml-2"
              >
                {isRegistering ? "Stop Registering" : "Adjust Registration"}
              </button>
            </TabsList>
            <TabsContent value="EM" className={cn("flex flex-col", selectedIsotope === "EM" ? "grow" : "hidden")}>
              <ControlledOpenSeaDragon 
                iiifContent={`${mimsImage?.em_dzi}`}
                canvasStore={canvasStore}
                mode="navigate"
              />
            </TabsContent>
            {mimsImage?.mims_tiff_images?.map((tiffImage: any) => {
              const isActive = selectedIsotope === tiffImage.name;
              const image = tiffImage.image;
              return (
                <TabsContent key={tiffImage.id} value={tiffImage.name} className={cn("flex flex-col", isActive ? "grow" : "hidden")}>
                  <div className="min-h-[600px] flex flex-col grow">
                    <ControlledOpenSeaDragon 
                    url={`${image}`}
                    canvasStore={mimsStore}
                    mode="navigate"
                  />
                  </div>
                </TabsContent>
              );
            })}
          </Tabs>
        </div>
      </div>
      {mimsImage && (
      <CreateRatioImage 
        open={isRatioDialogOpen}
        onOpenChange={setIsRatioDialogOpen}
        mimsImageId={mimsImageId as string}
        tiffImages={mimsImage.mims_tiff_images || []}
      />
    )}
    </div>
    
  );
};

export default DetailAligned;