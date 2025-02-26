import { createFileRoute } from '@tanstack/react-router'
import MimsImageSetDetail from '@/pages/MimsImageSetDetail/Page'
export const Route = createFileRoute('/canvas/$canvasId/mimsImageSet/$mimsImageSetId')({
  component: MimsImageSetDetail,
})