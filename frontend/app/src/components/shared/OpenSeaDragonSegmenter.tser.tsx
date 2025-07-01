import React, { useEffect, useState } from "react";
import { useStore } from "react-redux";
import { v4 as uuidv4 } from "uuid";
import { api } from "../../services/api";

const OpenSeaDragonSegmenter = () => {
  const storeState = useStore().getState();
  const [mode, setMode] = useState("navigate");
  const [isInclude, setIsInclude] = useState(true);
  const [mimsImageId, setMimsImageId] = useState("");
  const [isotope, setIsotope] = useState("");

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
        storeState.points.forEach((p: any) => (p.type !== "point_confirmed" ? storeState.removePoint(p.id) : null));
        // Remove suggestions
        const suggestions = storeState.overlays.filter((o: any) => o.type === "suggestion");
        suggestions.forEach((o: any) => storeState.removeOverlay(o.id));

        // Remove brush strokes
        const brushStrokes = storeState.overlays.filter((o: any) => o.type === "brush_stroke");
        brushStrokes.forEach((o: any) => storeState.removeOverlay(o.id));
      } 
      else if (e.key === " ") {
        // Prevent default spacebar scrolling
        e.preventDefault();
        storeState.points.forEach((p: any) => (p.type !== "point_confirmed" ? storeState.removePoint(p.id) : null));

        // 1) Confirm any "suggestion" shape (existing logic)
        const shape = storeState.overlays.find((p: any) => p.type === "suggestion");
        if (shape) {
          storeState.removeOverlay(shape.id);
          storeState.addOverlay({
            ...shape,
            color: "green",
            type: "shape_confirmed"
          });
        }

        // 2) Confirm all brush strokes => convert to polygons, color them green
        const brushStrokes = storeState.overlays.filter((o: any) => o.type === "brush_stroke");
        brushStrokes.forEach((stroke: any) => {
          // Remove the stroke overlay
          storeState.removeOverlay(stroke.id);
          // Add it as a new "shape_confirmed" overlay, green fill
          storeState.addOverlay({
            ...stroke,
            color: "green",
            type: "shape_confirmed"
          });
        });

        // 3) Confirm all points => convert to polygons, color them green
        const points = storeState.points.filter((p: any) => p.type === "pending");
        points.forEach((point: any) => {
          storeState.removePoint(point.id);
          storeState.addPoint({
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
  }, [storeState, mode]);

  // -- If the user sets points (include/exclude clicks), call segmentation API --
  useEffect(() => {
    const shapePoints = storeState.points.filter((p: any) => ["include", "exclude"].includes(p.type));
    if (mode !== "shapes" || shapePoints.length === 0) return;
    const point_coords = shapePoints.map((point: any) => [point.x, point.y]);
    const point_labels = shapePoints.map((point: any) =>
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
        storeState
          .overlays
          .filter((o: any) => o.type === "suggestion")
          .forEach((o: any) => storeState.removeOverlay(o.id));

        // Add new suggestion
        storeState.addOverlay({
          id: uuidv4(),
          data: { polygon: res.data?.polygons[0] },
          fill: true,
          color: "red",
          type: "suggestion"
        });
      });
  }, [storeState.points.length]);

  return (
    <div>
      {/* Render your component content here */}
    </div>
  );
};

export default OpenSeaDragonSegmenter; 