import { createFileRoute, } from "@tanstack/react-router";
import EMImageDetail from "@/pages/CanvasDetail/Page";

export const Route = createFileRoute("/em_image/$emImageId")({
  component: EMImageDetail,
});
