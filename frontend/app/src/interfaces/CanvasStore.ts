import { CanvasOverlay } from "@/interfaces/CanvasOverlay";
import { Point } from "@/interfaces/Point";

export interface CanvasStore {
  zoom: number;
  flip: boolean;
  rotation: number;
  coordinates?: Point[];
  overlays: CanvasOverlay[];
  points: Point[];
  setZoom: (zoom: number) => void;
  setFlip: (flip: boolean) => void;
  setRotation: (rotation: number) => void;
  addPoint: (point: Point) => void;
  setCoordinates: (coordinates: Point[]) => void;
  addOverlay: (overlay: CanvasOverlay) => void;
  removeOverlay: (overlayId: string) => void;
  clearPoints: () => void;
}