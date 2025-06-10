import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/shared/ui/dialog";

interface CreateRatioImageProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mimsImageId: string;
  tiffImages: any[];
}

const CreateRatioImage: React.FC<CreateRatioImageProps> = ({
  open,
  onOpenChange,
  mimsImageId,
  tiffImages,
}) => {
  const [numeratorIsotope, setNumeratorIsotope] = useState("");
  const [denominatorIsotope, setDenominatorIsotope] = useState("");
  const [scaleFactor, setScaleFactor] = useState(10000);
  const queryClient = useQueryClient();

  const createRatioMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post(`mims_image/${mimsImageId}/create-ratio/`, {
        numerator_isotope: numeratorIsotope,
        denominator_isotope: denominatorIsotope,
        scale_factor: scaleFactor,
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mims_image', mimsImageId] });
      onOpenChange(false);
    },
  });

  const handleCreate = () => {
    if (numeratorIsotope && denominatorIsotope) {
      createRatioMutation.mutate();
    }
  };

  const resetForm = () => {
    setNumeratorIsotope("");
    setDenominatorIsotope("");
    setScaleFactor(10000);
  };

  return (
    <Dialog open={open} onOpenChange={(newOpen) => {
      if (!newOpen) resetForm();
      onOpenChange(newOpen);
    }}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create Ratio Image</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <label htmlFor="numerator" className="text-right">
              Numerator:
            </label>
            <select
              id="numerator"
              className="col-span-3 p-2 border rounded"
              value={numeratorIsotope}
              onChange={(e) => setNumeratorIsotope(e.target.value)}
            >
              <option value="">Select an isotope</option>
              {tiffImages.map((img) => (
                <option key={`num-${img.id}`} value={img.id}>
                  {img.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <label htmlFor="denominator" className="text-right">
              Denominator:
            </label>
            <select
              id="denominator"
              className="col-span-3 p-2 border rounded"
              value={denominatorIsotope}
              onChange={(e) => setDenominatorIsotope(e.target.value)}
            >
              <option value="">Select an isotope</option>
              {tiffImages.map((img) => (
                <option key={`den-${img.id}`} value={img.id}>
                  {img.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <label htmlFor="scale" className="text-right">
              Scale Factor:
            </label>
            <input
              id="scale"
              type="number"
              className="col-span-3 p-2 border rounded"
              value={scaleFactor}
              onChange={(e) => setScaleFactor(Number(e.target.value))}
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose className="px-4 py-2 border rounded bg-gray-200 hover:bg-gray-300">
            Cancel
          </DialogClose>
          <button
            onClick={handleCreate}
            disabled={!numeratorIsotope || !denominatorIsotope || createRatioMutation.isPending}
            className={`px-4 py-2 rounded text-black border-blue hover:bg-blue-700 disabled:cursor-not-allowed ${
              createRatioMutation.isPending ? "opacity-70" : ""
            }`}
          >
            {createRatioMutation.isPending ? "Creating..." : "Create"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default CreateRatioImage;