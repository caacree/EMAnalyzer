import React, { useEffect, useRef, useState } from "react";
import { useCanvasViewer } from "@/stores/canvasViewer";
import { useMimsViewer } from "@/stores/mimsViewer";

const HIGHLIGHT = "hotpink";

type ItemType = "overlay" | "point";

interface HighlightCache {
  type: ItemType;
  canvasId: string;
  mimsId: string;
  canvasColor: string;
  mimsColor: string;
}

/**
 * Index inspector for registered shapes/points.
 * Hover ⇒ highlight pair; Delete/Backspace while hovering ⇒ remove pair.
 * Uses internal `hovered` state so colour changes fire once per index change.
 */
export default function ShapePointIndexList() {
  /* -------- only subscribe to length + colour setters to avoid re‑renders ---- */
  const canvasSel = useCanvasViewer((s) => ({
    overlayCount: s.overlays.length,
    pointCount: s.points.length,
    setOverlayColor: s.updateOverlayColor,
    setPointColor: s.updatePointColor,
  }));

  const mimsSel = useMimsViewer((s) => ({
    overlayCount: s.overlays.length,
    pointCount: s.points.length,
    setOverlayColor: s.updateOverlayColor,
    setPointColor: s.updatePointColor,
  }));

  /* ------- direct access to full arrays & removal fns without subscription ---- */
  const canvasState = useCanvasViewer.getState;
  const mimsState = useMimsViewer.getState;

  const [hovered, setHovered] = useState<{ type: ItemType; index: number } | null>(
    null
  );

  const prevRef = useRef<HighlightCache | null>(null);

  /* ----------------------------- colour helpers ----------------------------- */
  const setColourById = (
    type: ItemType,
    canvasId: string,
    mimsId: string,
    canvasColour: string,
    mimsColour: string
  ) => {
    if (type === "overlay") {
      canvasSel.setOverlayColor(canvasId, canvasColour);
      mimsSel.setOverlayColor(mimsId, mimsColour);
    } else {
      canvasSel.setPointColor(canvasId, canvasColour);
      mimsSel.setPointColor(mimsId, mimsColour);
    }
  };

  useEffect(() => {
    // restore previous highlight
    if (prevRef.current) {
      const { type, canvasId, mimsId, canvasColor, mimsColor } = prevRef.current;
      setColourById(type, canvasId, mimsId, canvasColor, mimsColor);
      prevRef.current = null;
    }

    // apply new highlight
    if (hovered) {
      const { type, index } = hovered;
      const canvasArr = type === "overlay" ? canvasState().overlays : canvasState().points;
      const mimsArr = type === "overlay" ? mimsState().overlays : mimsState().points;
      const canvasObj = canvasArr[index];
      const mimsObj = mimsArr[index];
      if (!canvasObj || !mimsObj) return;

      prevRef.current = {
        type,
        canvasId: canvasObj.id,
        mimsId: mimsObj.id,
        canvasColor: canvasObj.color,
        mimsColor: mimsObj.color,
      };
      setColourById(type, canvasObj.id, mimsObj.id, HIGHLIGHT, HIGHLIGHT);
    }
  }, [hovered]);

  /* ---------------------  Delete key removes hovered pair  ------------------- */
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (!hovered) return;
      if (e.key !== "Delete" && e.key !== "Backspace") return;

      const { type, index } = hovered;
      const canvasArr = type === "overlay" ? canvasState().overlays : canvasState().points;
      const mimsArr = type === "overlay" ? mimsState().overlays : mimsState().points;
      const canvasObj = canvasArr[index];
      const mimsObj = mimsArr[index];
      if (!canvasObj || !mimsObj) return;

      if (type === "overlay") {
        canvasState().removeOverlay(canvasObj.id);
        mimsState().removeOverlay(mimsObj.id);
      } else {
        canvasState().removePoint(canvasObj.id);
        mimsState().removePoint(mimsObj.id);
      }
      setHovered(null); // clear state so effect restores colours next time
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [hovered]);

  /* -------------------------------- UI rows --------------------------------- */
  const Row = ({ label, type, count }: { label: string; type: ItemType; count: number }) => (
    <div className="flex items-center mb-2 select-none">
      <span className="w-20 text-sm font-medium">{label}</span>
      <ul className="flex flex-wrap gap-1">
        {Array.from({ length: count }).map((_, i) => (
          <li
            key={i}
            onMouseEnter={() =>
              setHovered((curr) =>
                curr && curr.type === type && curr.index === i ? curr : { type, index: i }
              )
            }
            onMouseLeave={() => setHovered(null)}
            className="w-6 text-center text-xs bg-gray-200 rounded cursor-pointer"
          >
            {i}
          </li>
        ))}
      </ul>
    </div>
  );

  /* ----------------------------- render lists ------------------------------- */
  return (
    <div className="mt-4 border-t pt-3">
      <Row label="Shapes" type="overlay" count={canvasSel.overlayCount} />
      <Row label="Points" type="point" count={canvasSel.pointCount} />
    </div>
  );
}
