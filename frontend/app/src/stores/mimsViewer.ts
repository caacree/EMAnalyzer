import { CanvasOverlay } from '@/interfaces/CanvasOverlay'
import { create } from 'zustand'

interface Point {
  id: string
  x: number
  y: number
  type?: string
  color?: string
}

interface MimsViewerState {
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
}

export const useMimsViewer = create<MimsViewerState>((set) => ({
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
    const overlayDefaults = {
      visible: true,
      fill: true,
      color: "red"
    }
    const newOverlay = {
      ...overlayDefaults,
      ...overlay,
    }
    const newOverlays = [...state.overlays, newOverlay];
    return {
      overlays: newOverlays
    }
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
  clearOverlays: () => set({ overlays: [] })
}))
