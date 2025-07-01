import React, { useEffect, useState, useMemo } from "react";
import api from "../../api/api";
import { useParams } from "@tanstack/react-router";
import ControlledOpenSeaDragon from "./ControlledOpenSeaDragon";
import { Pencil, MousePointer, Hexagon, Target } from "lucide-react";
import { IconTooltip } from "./ui/tooltip";
import { v4 as uuidv4 } from 'uuid';

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
  const [mode, setMode] = useState<"shapes" | "draw" | "navigate" | "points">("navigate");
  const [brushSize, setBrushSize] = React.useState(10);

  // -- Keydown event handler, extended for "brush_stroke" overlays --
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const currentState = canvasStore.getState()
      if (e.key === "i") {
        setIsInclude(true);
      } else if (e.key === "o") {
        setIsInclude(false);
      } 
      else if (e.key === "r") {
        // "r" => reset all segment suggestions AND brush strokes
        setIsInclude(true);
        currentState.points.forEach((p: any) => (p.type !== "point_confirmed" ? currentState.removePoint(p.id) : null));
        // Remove suggestions
        const suggestions = currentState.overlays?.filter((o: any) => o.type === "suggestion");
        suggestions.forEach((o: any) => currentState.removeOverlay(o.id));

        // Remove brush strokes
        const brushStrokes = currentState.overlays?.filter((o: any) => o.type === "brush_stroke");
        brushStrokes.forEach((o: any) => currentState.removeOverlay(o.id));
      } 
      else if (e.key === " ") {
        // Prevent default spacebar scrolling
        e.preventDefault();
        currentState.points.forEach((p: any) => (p.type !== "point_confirmed" ? currentState.removePoint(p.id) : null));

        // 1) Confirm any "suggestion" shape (existing logic)
        const shape = currentState.overlays.find((p: any) => p.type === "suggestion");
        if (shape) {
          currentState.removeOverlay(shape.id);
          currentState.addOverlay({
            ...shape,
            color: "green",
            type: "shape_confirmed"
          });
        }

        // 2) Confirm all brush strokes => convert to polygons, color them green
        const brushStrokes = currentState.overlays?.filter((o: any) => o.type === "brush_stroke");
        brushStrokes.forEach((stroke: any) => {
          // Remove the stroke overlay
          currentState.removeOverlay(stroke.id);
          // Add it as a new "shape_confirmed" overlay, green fill
          currentState.addOverlay({
            ...stroke,
            color: "green",
            type: "shape_confirmed"
          });
        });

        // 3) Confirm all points => convert to polygons, color them green
        const points = currentState.points?.filter((p: any) => p.type === "pending");
        points.forEach((point: any) => {
          currentState.removePoint(point.id);
          currentState.addPoint({
            id: uuidv4(),
            x: point.x,
            y: point.y,
            color: "green",
            type: "point_confirmed"
          });
        });
      }
    };
    if (mode === "shapes" || mode === "draw" || mode === "points") {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [canvasStore, mode]);

  // -- If the user sets points (include/exclude clicks), call segmentation API --
  useEffect(() => {
    const currentState = canvasStore.getState();
    const shapePoints = currentState.points?.filter((p: any) => ["include", "exclude"].includes(p.type));
    if (mode !== "shapes" || shapePoints?.length === 0) return;
    const point_coords = shapePoints?.map((point: any) => [point.x, point.y]);
    const point_labels = shapePoints?.map((point: any) =>
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
        const currentState = canvasStore.getState();
        currentState
          .overlays
          ?.filter((o: any) => o.type === "suggestion")
          .forEach((o: any) => currentState.removeOverlay(o.id));

        // Add new suggestion
        currentState.addOverlay({
          id: uuidv4(),
          data: { polygon: res.data?.polygons[0] },
          fill: true,
          color: "red",
          type: "suggestion"
        });
      });
  }, [canvasStore.getState().points?.length]);


  return (
    <div className="flex flex-col grow h-full">
      {/* Mode selection menu bar */}
      <div className="flex items-center gap-4 mb-4">
        <div className="flex bg-gray-100 rounded-md p-1 space-x-2">
          <IconTooltip content="Shape Selection Mode" isActive={mode === "shapes"} onClick={() => setMode("shapes")}>
            <Hexagon size={20} />
          </IconTooltip>
          <IconTooltip content="Point Selection Mode" isActive={mode === "points"} onClick={() => setMode("points")}>
            <Target size={20} />
          </IconTooltip>
          <IconTooltip content="Draw Mode" isActive={mode === "draw"} onClick={() => setMode("draw")}>
            <Pencil size={20} />
          </IconTooltip>
          <IconTooltip content="Navigate Mode" isActive={mode === "navigate"} onClick={() => setMode("navigate")}>
            <MousePointer size={20}/>
          </IconTooltip>
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
        brushSize={brushSize}
      />
    </div>
  );
};

export default OpenSeaDragonSegmenter;
