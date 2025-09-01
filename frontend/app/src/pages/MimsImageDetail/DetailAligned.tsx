/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import api, { get_mims_image_dewarped_url } from "@/api/api";
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
  const canvasStoreApi = useCanvasViewer;
  const canvasStore = canvasStoreApi();
  const mimsStoreApi = useMimsViewer;
  const mimsStore = mimsStoreApi();
  const { setCoordinates: setEmCoordinates } = canvasStore;
  const { setFlip: setMimsFlip, setRotation: setMimsRotation } = mimsStore;
  const [openseadragonOptions, setOpenseadragonOptions] = useState<any>({defaultZoomLevel: 1});
  const [selectedIsotopes, setSelectedIsotopes] = useState<string[]>(["EM"]);
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
      setSelectedIsotopes(["EM"]);
      
      // Set coordinates from registration_bbox of the first mims_tiff_image if available
      if (mimsImage?.mims_tiff_images?.length > 0 && mimsImage.mims_tiff_images[0].registration_bbox) {
        const bbox = mimsImage.mims_tiff_images[0].registration_bbox;
        // Assuming registration_bbox is in the format [[top_left_x, top_left_y], [bottom_right_x, bottom_right_y]]
        const em_bbox = [
          {x: bbox[0][0], y: bbox[0][1], id: "em_tl"}, 
          {x: bbox[2][0], y: bbox[2][1], id: "em_br"}
        ];
        setEmCoordinates(em_bbox);
      }
    }
  }, [mimsImage]);

  const toggleIsotope = useCallback((isotopeName: string) => {
    setSelectedIsotopes(prev => {
      if (prev.includes(isotopeName)) {
        // Don't allow removing EM if it's the only selected isotope
        if (isotopeName === "EM" && prev.length === 1) {
          return prev;
        }
        return prev.filter(name => name !== isotopeName);
      } else {
        return [...prev, isotopeName];
      }
    });
  }, []);

  const getDownloadUrl = useCallback(() => {
    if (!mimsImage || selectedIsotopes.length === 0) return "";
    
    // If only EM is selected, return EM download URL
    if (selectedIsotopes.length === 1 && selectedIsotopes[0] === "EM") {
      return get_mims_image_dewarped_url(mimsImage, {name: "EM", id: "EM"});
    }
    
    // For multiple selections, we'll need to handle this differently
    // For now, return the first non-EM isotope URL
    const nonEmIsotopes = selectedIsotopes.filter(name => name !== "EM");
    if (nonEmIsotopes?.length > 0) {
      const selectedTiffImage = mimsImage.mims_tiff_images.find((img: any) => img.name === nonEmIsotopes[0]);
      if (selectedTiffImage) {
        return get_mims_image_dewarped_url(mimsImage, selectedTiffImage);
      }
    }
    
    return "";
  }, [mimsImage, selectedIsotopes]);
  
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
      const isotopeNames = selectedIsotopes.join('_');
      const filename = `${mimsImage?.name || mimsImage?.file?.split('/').pop().split('.')[0]}_${isotopeNames}.png`;
      
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
  }, [getDownloadUrl, mimsImage, selectedIsotopes]);

  // Prepare data for ControlledOpenSeaDragon
  const openSeaDragonData = useMemo(() => {
    if (!mimsImage) return { iiifContent: undefined, positionedImages: undefined };
    
    const hasEm = selectedIsotopes.includes("EM");
    const selectedTiffImages = mimsImage.mims_tiff_images?.filter((img: any) => 
      selectedIsotopes.includes(img.name)
    ) || [];
    console.log(mimsImage)

    const geotiffs = mimsImage.mims_overlays?.map((overlay: any) => {
      return {
        url: overlay.mosaic,
        name: overlay.isotope,
        bounds: mimsImage?.image_set?.canvas_bbox
      };
    });
    
    // Create positioned images data with registration_bbox information
    const positionedImages = selectedTiffImages?.map((tiffImage: any) => {
      const imageUrl = `${api.defaults.baseURL}mims_image/${mimsImageId}/unwarped/${tiffImage.id}/image.png`;
      
      // Calculate bounds from registration_bbox
      let bounds = null;
      if (tiffImage.registration_bbox) {
        const bbox = tiffImage.registration_bbox;
        // registration_bbox format: [[top_left_x, top_left_y], [top_right_x, top_right_y], [bottom_right_x, bottom_right_y], [bottom_left_x, bottom_left_y]]
        
        // Find the bounding rectangle that encompasses all 4 points
        const xCoords = bbox.map((point: number[]) => point[0]);
        const yCoords = bbox.map((point: number[]) => point[1]);
        
        const minX = Math.min(...xCoords);
        const maxX = Math.max(...xCoords);
        const minY = Math.min(...yCoords);
        const maxY = Math.max(...yCoords);
        
        // Convert to OpenSeaDragon bounds format: [x, y, width, height]
        // Using the EM image dimensions for normalization
        const emWidth = mimsImage.image_set?.canvas?.width || 1;
        const emHeight = mimsImage.image_set?.canvas?.height || 1;
        
        bounds = [
          minX / emWidth,           // x (normalized)
          minY / emHeight,          // y (normalized)
          (maxX - minX) / emWidth,  // width (normalized)
          (maxY - minY) / emHeight  // height (normalized)
        ];
      }
      
      return {
        url: imageUrl,
        name: tiffImage.name,
        bounds: bounds
      };
    });
    
    return {
      iiifContent: hasEm ? mimsImage.em_dzi : undefined,
      positionedImages: positionedImages?.length > 0 ? positionedImages : undefined,
      geotiffs: geotiffs?.length > 0 ? geotiffs : undefined
    };
  }, [mimsImage, selectedIsotopes, mimsImageId]);

  if (!mimsImage) {
    return <div>Loading...</div>;
  }

  const { iiifContent, positionedImages } = openSeaDragonData;
  

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
          <div className="flex flex-col grow min-h-[600px] justify-center">
            <div className="flex space-x-1 mb-4">
              <button 
                onClick={() => toggleIsotope("EM")}
                className={cn(
                  "px-3 py-1 rounded border-2 transition-colors",
                  selectedIsotopes.includes("EM") 
                    ? "bg-blue-500 text-white border-blue-500" 
                    : "border-gray-300 text-gray-700 hover:bg-gray-100"
                )}
              >
                EM
              </button>
              {mimsImage?.mims_tiff_images?.map((tiffImage: any) => (
                <button
                  key={tiffImage.id}
                  onClick={() => toggleIsotope(tiffImage.name)}
                  className={cn(
                    "px-3 py-1 rounded border-2 transition-colors",
                    selectedIsotopes.includes(tiffImage.name) 
                      ? "bg-blue-500 text-white border-blue-500" 
                      : "border-gray-300 text-gray-700 hover:bg-gray-100"
                  )}
                >
                  {tiffImage.name}
                </button>
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
            </div>
            <div className="min-h-[600px] flex flex-col grow">
              <ControlledOpenSeaDragon 
                key={`${mimsImageId}-${selectedIsotopes.join('-')}`}
                iiifContent={iiifContent}
                positionedImages={positionedImages}
                canvasStore={canvasStoreApi}
                mode="navigate"
              />
            </div>
          </div>
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