import { createFileRoute, } from "@tanstack/react-router";
import MimsImageDetail from "@/pages/MimsImageDetail/Page";

export const Route = createFileRoute("/mims_image/$mimsImageId")({
  component: MimsImageDetail,
});
