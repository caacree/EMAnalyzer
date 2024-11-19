import { create } from 'zustand'

interface Point {
  x: number
  y: number
}

interface Overlay {
  id: string
  visible: boolean
  data: any // You might want to make this more specific based on your needs
}

interface CanvasViewerState {
  zoom: number
  flip: boolean
  rotation: number
  points: Point[]
  overlays: Overlay[]
  setZoom: (zoom: number) => void
  setFlip: (flip: boolean) => void
  setRotation: (rotation: number) => void
  addPoint: (point: Point) => void
  removePoint: (index: number) => void
  clearPoints: () => void
  addOverlay: (overlay: Overlay) => void
  removeOverlay: (id: string) => void
  toggleOverlay: (id: string) => void
  clearOverlays: () => void
}

export const useCanvasViewer = create<CanvasViewerState>((set) => ({
  zoom: 1,
  flip: false,
  rotation: 0,
  points: [],
  overlays: [],
  
  setZoom: (zoom) => set({ zoom }),
  setFlip: (flip) => set({ flip }),
  setRotation: (rotation) => set({ rotation }),
  
  addPoint: (point) => set((state) => ({ 
    points: [...state.points, point] 
  })),
  removePoint: (index) => set((state) => ({
    points: state.points.filter((_, i) => i !== index)
  })),
  clearPoints: () => set({ points: [] }),
  
  addOverlay: (overlay) => set((state) => ({
    overlays: [...state.overlays, overlay]
  })),
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
  clearOverlays: () => set({ overlays: [] })
}))
