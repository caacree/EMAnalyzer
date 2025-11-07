import { CanvasOverlay } from '@/interfaces/CanvasOverlay'
import { create } from 'zustand'
import { Point } from '@/interfaces/Point'
import { v4 as uuidv4 } from 'uuid';

export interface CanvasViewerState {
  zoom: number
  flip: boolean
  rotation: number
  coordinates: Point[]
  points: Point[]
  overlays: CanvasOverlay[]
  setZoom: (zoom: number) => void
  setFlip: (flip: boolean) => void
  setRotation: (rotation: number) => void
  setCoordinates: (coordinates: Point[]) => void
  addPoint: (point: Point) => void
  removePoint: (id: string) => void
  clearPoints: () => void
  addOverlay: (overlay: any) => void
  removeOverlay: (id: string) => void
  toggleOverlay: (id: string) => void
  clearOverlays: () => void
  updateOverlayColor: (id: string, color: string) => void
  updatePointColor: (id: string, color: string) => void
  setSegmentationOverlays: (overlays: CanvasOverlay[]) => void
}

export const useCanvasViewer = create<CanvasViewerState>((set) => ({
  zoom: 1,
  flip: false,
  rotation: 0,
  coordinates: [],
  points: [],
  overlays: [],
  
  setZoom: (zoom) => set({ zoom }),
  setFlip: (flip) => set({ flip }),
  setRotation: (rotation) => set({ rotation }),
  setCoordinates: (coordinates) => set({ coordinates }),
  
  addPoint: (point) => set((state) => ({ 
    points: [...state.points, point] 
  })),
  removePoint: (id: string) => set((state) => ({
    points: state.points.filter((p) => p.id !== id)
  })),
  clearPoints: () => set({ points: [] }),
  
  addOverlay: (overlay) => set((state) => {
    const overlayDefaults = { visible: true, fill: true, color: "red" };
    const newOverlay = {
      // ← guarantee an id
      id: overlay.id ?? uuidv4(),
      ...overlayDefaults,
      ...overlay,
    };
    return { overlays: [...state.overlays, newOverlay] };
  }),
  removeOverlay: (id) => set((state) => ({
    overlays: state.overlays.filter(overlay => overlay.id !== id)
  })),
  toggleOverlay: (id) => set((state) => ({
    overlays: state.overlays.map(overlay =>
      overlay.id === id 
        ? { ...overlay, visible: !overlay.visible }
        : overlay
    )
  })),
  clearOverlays: () => set({ overlays: [] }),
  updateOverlayColor: (id: string, color: string) =>
    set(state => ({
      overlays: state.overlays.map(o =>
        o.id === id ? { ...o, color } : o
      ),
    })),
  
  updatePointColor: (id: string, color: string) =>
    set(state => ({
      points: state.points.map(p =>
        p.id === id ? { ...p, color } : p
      ),
    })),
  
  setSegmentationOverlays: (overlays: CanvasOverlay[]) =>
    set(state => ({
      overlays: [
        ...state.overlays.filter(o => o.type !== 'segmentation'),
        ...overlays
      ]
    })),
}))

// Export the store API for components that need getState
export const canvasViewerStore = useCanvasViewer;
