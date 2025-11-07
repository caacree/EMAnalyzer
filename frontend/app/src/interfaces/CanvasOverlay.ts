export interface CanvasOverlay {
  id: string;
  data: any;
  visible: boolean;
  fill?: boolean;
  color?: string;
  type?: string;  // e.g. "shape_confirmed", "brush_stroke", "suggestion", "segmentation"...
  strokeWidth?: number;
  opacity?: number;
}