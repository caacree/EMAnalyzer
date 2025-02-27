export interface CanvasOverlay {
  id: string;
  data: any;    // e.g. { bbox?: number[][], polygon?: number[][], path?: number[][] }
  fill?: boolean;
  color?: string;
  type?: string;  // e.g. "shape_confirmed", "brush_stroke", "suggestion"...
  strokeWidth?: number;
}