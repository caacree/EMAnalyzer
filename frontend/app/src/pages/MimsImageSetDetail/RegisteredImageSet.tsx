/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/shared/ui/tabs";
import { Checkbox } from "@/components/shared/ui/checkbox";
import { Trash2 } from "lucide-react";
import { useMimsViewer, useCanvasViewer } from "@/stores/canvasViewer";
import ControlledOpenSeaDragon from '@/components/shared/ControlledOpenSeaDragon';
import { buildMediaURL } from "@/api/api";

// Component for registered MIMS Image Sets - shows isotope tabs
const RegisteredImageSet = ({ selectedMimsSet, onDelete, canvas }: { selectedMimsSet: any, onDelete: () => void, canvas: any }) => {
  const [selectedIsotopes, setSelectedIsotopes] = useState<string[]>(["EM"]);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Set default isotope to EM
  React.useEffect(() => {
    setSelectedIsotopes(["EM"]);
  }, [selectedMimsSet]);

  const toggleIsotope = (isotope: string) => {
    setSelectedIsotopes(prev => 
      prev.includes(isotope) 
        ? prev.filter(i => i !== isotope)
        : [...prev, isotope]
    );
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    onDelete();
    setShowDeleteConfirm(false);
  };

  return (
    <div className="flex flex-col w-full">
      {/* Header with delete button */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">MIMS Image Set: {selectedMimsSet.name || selectedMimsSet.id}</h2>
        <button
          onClick={handleDeleteClick}
          className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded flex items-center gap-2"
        >
          <Trash2 size={16} />
          Delete Image Set
        </button>
      </div>

      {/* Isotope selection checkboxes */}
      <div className="mb-4">
        {selectedMimsSet.mims_overlays?.length > 0 ? (
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center space-x-2">
              <Checkbox 
                id="EM"
                checked={selectedIsotopes.includes("EM")}
                onCheckedChange={() => toggleIsotope("EM")}
              />
              <label htmlFor="EM" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                EM
              </label>
            </div>
            {selectedMimsSet.mims_overlays.map((overlay: any) => (
              <div key={overlay.id} className="flex items-center space-x-2">
                <Checkbox 
                  id={overlay.isotope}
                  checked={selectedIsotopes.includes(overlay.isotope)}
                  onCheckedChange={() => toggleIsotope(overlay.isotope)}
                />
                <label htmlFor={overlay.isotope} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                  {overlay.isotope}
                </label>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-500">No isotope data available</div>
        )}
      </div>

      {/* Single OpenSeaDragon viewer with EM base and selected isotope overlay */}
      <div className="flex grow min-h-[600px]">
        <ControlledOpenSeaDragon 
          iiifContent={buildMediaURL(canvas?.images?.[0]?.dzi_file)}
          geotiffs={selectedIsotopes.filter(isotope => isotope !== "EM").length > 0 ? 
            selectedMimsSet.mims_overlays
              ?.filter((overlay: any) => selectedIsotopes.includes(overlay.isotope))
              ?.map((overlay: any) => ({
                url: buildMediaURL(overlay.dzi_url),
                name: overlay.isotope,
                bounds: selectedMimsSet.canvas_bbox
              })) 
            : undefined
          }
          canvasStore={useCanvasViewer}
          mode="navigate"
        />
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-lg max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Confirm Delete</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete this MIMS Image Set? This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RegisteredImageSet;