import { createFileRoute } from '@tanstack/react-router'
import CanvasDetail from "@/pages/CanvasDetail/Page";
import MimsImageSetDetail from "@/pages/MimsImageSetDetail/Page";

export const Route = createFileRoute('/canvas/$canvasId')({
  component: ({ search }) => {
    if (search.mimsImageSet) {
      return <MimsImageSetDetail />;
    }
    return <CanvasDetail />;
  }
})
