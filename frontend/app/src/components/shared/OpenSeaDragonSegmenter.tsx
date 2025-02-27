import React, { useEffect, useState } from "react";
import api from "../../api/api";
import { useParams } from "@tanstack/react-router";
import ControlledOpenSeaDragon from "./ControlledOpenSeaDragon";
import { strokePathToPolygon } from "@/utils/strokeToPolygon";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/shared/ui/tooltip";
import { Pencil, MousePointer, ShapeIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const OpenSeaDragonSegmenter = ({
  url,
  iiifContent,
  canvasStore,
  isotope,
}: {
  url?: any;
  iiifContent?: any;
  canvasStore?: any;
  isotope?: any;
}) => {
  const { mimsImageId } = useParams({ strict: false });

  const [isInclude, setIsInclude] = React.useState<boolean>(true);
  const [mode, setMode] = useState<"shapes" | "draw" | "navigate">("shapes");
  const [brushSize, setBrushSize] = React.useState(10);

  // -- Keydown event handler, extended for "brush_stroke" overlays --
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "i") {
        setIsInclude(true);
      } else if (e.key === "o") {
        setIsInclude(false);
      } 
      else if (e.key === "r") {
        // "r" => reset all segment suggestions AND brush strokes
        setIsInclude(true);
        canvasStore.clearPoints();

        // Remove suggestions
        const suggestions = canvasStore.overlays.filter((o: any) => o.type === "suggestion");
        suggestions.forEach((o: any) => canvasStore.removeOverlay(o.id));

        // Remove brush strokes
        const brushStrokes = canvasStore.overlays.filter((o: any) => o.type === "brush_stroke");
        brushStrokes.forEach((o: any) => canvasStore.removeOverlay(o.id));
      } 
      else if (e.key === " ") {
        // Prevent default spacebar scrolling
        e.preventDefault();
        canvasStore.clearPoints();

        // 1) Confirm any "suggestion" shape (existing logic)
        const shape = canvasStore.overlays.find((p: any) => p.type === "suggestion");
        if (shape) {
          canvasStore.removeOverlay(shape.id);
          canvasStore.addOverlay({
            ...shape,
            color: "green",
            type: "shape_confirmed"
          });
        }

        // 2) Confirm all brush strokes => convert to polygons, color them green
        const brushStrokes = canvasStore.overlays.filter((o: any) => o.type === "brush_stroke");
        brushStrokes.forEach((stroke: any) => {
          // Remove the stroke overlay
          canvasStore.removeOverlay(stroke.id);

          // Build a polygon at full brush width
          const { path } = stroke.data;
          console.log(stroke.strokeWidth);
          const polygon = strokePathToPolygon(path, stroke.strokeWidth || 10);

          // Add it as a new "shape_confirmed" overlay, green fill
          canvasStore.addOverlay({
            id: Math.random().toString(),
            data: { polygon },
            fill: true,
            color: "green",
            type: "shape_confirmed"
          });
        });
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [canvasStore]);

  // -- If the user sets points (include/exclude clicks), call segmentation API --
  useEffect(() => {
    if (canvasStore.points.length === 0) return;
    const point_coords = canvasStore.points.map((point: any) => [point.x, point.y]);
    const point_labels = canvasStore.points.map((point: any) =>
      point.type === "include" ? 1 : 0
    );

    api
      .post(`mims_image/${mimsImageId}/get_segment_prediction/`, {
        image_key: isotope,
        point_coords,
        point_labels
      })
      .then(res => {
        // Remove old suggestions
        canvasStore
          .overlays
          .filter((o: any) => o.type === "suggestion")
          .forEach((o: any) => canvasStore.removeOverlay(o.id));

        // Add new suggestion
        canvasStore.addOverlay({
          id: Math.random().toString(),
          data: { polygon: res.data?.polygons[0] },
          fill: true,
          color: "red",
          type: "suggestion"
        });
      });
  }, [canvasStore.points.length]);


  return (
    <div className="flex flex-col grow h-full">
      {/* Mode selection menu bar */}
      <div className="flex items-center gap-4 mb-4">
        <div className="flex bg-gray-100 rounded-md p-1">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setMode("shapes")}
                  className={cn(
                    "p-2 rounded-md transition-colors",
                    mode === "shapes" ? "bg-white shadow-sm" : "hover:bg-gray-200"
                  )}
                >
                  <ShapeIcon size={20} />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Shape Selection Mode</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setMode("draw")}
                  className={cn(
                    "p-2 rounded-md transition-colors",
                    mode === "draw" ? "bg-white shadow-sm" : "hover:bg-gray-200"
                  )}
                >
                  <Pencil size={20} />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Draw Mode</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setMode("navigate")}
                  className={cn(
                    "p-2 rounded-md transition-colors",
                    mode === "navigate" ? "bg-white shadow-sm" : "hover:bg-gray-200"
                  )}
                >
                  <MousePointer size={20} />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Navigate Mode</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {mode === "draw" && (
          <div className="flex items-center gap-2">
            <label htmlFor="brush-size">Brush Size:</label>
            <input
              id="brush-size"
              type="number"
              value={brushSize}
              onChange={e => setBrushSize(parseInt(e.target.value, 10))}
              className="w-16 p-1 border rounded"
              min="1"
              max="50"
            />
          </div>
        )}
      </div>

      <ControlledOpenSeaDragon
        iiifContent={iiifContent}
        url={url}
        canvasStore={canvasStore}
        mode={mode}
        pointSelectionMode={isInclude ? "include" : "exclude"}
        allowBrush={mode === "draw"}
        brushSize={brushSize}
      />
    </div>
  );
};

export default OpenSeaDragonSegmenter;
