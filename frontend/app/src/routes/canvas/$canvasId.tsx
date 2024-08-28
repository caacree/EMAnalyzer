import { createFileRoute } from '@tanstack/react-router'
import CanvasDetail from "@/pages/CanvasDetail/Page";

export const Route = createFileRoute('/canvas/$canvasId')({
  component: CanvasDetail
})