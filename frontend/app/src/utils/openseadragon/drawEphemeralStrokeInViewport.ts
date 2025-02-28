import OpenSeadragon from "openseadragon";
import { strokePathToPolygon } from "../strokeToPolygon";
import { drawPolygonOrBboxOverlay } from "./drawPolygonOrBboxOverlay";

export default function drawEphemeralStrokeInViewport(
  viewer: OpenSeadragon.Viewer,
  strokeWidth: number,
  flip: boolean,
  rotation: number,
  imgPath?: [number, number, number][],
) {
  if (!imgPath) {
    viewer.removeOverlay("ephemeral-stroke");
  }
  if (!imgPath || imgPath.length < 2) return;
  const overlay = {
    id: "ephemeral-stroke",
    color: "red",
    visible: true,
    fill: true,
    data: { polygon: strokePathToPolygon(imgPath, strokeWidth) },
    type: "brush_stroke",
    strokeWidth
  }
  drawPolygonOrBboxOverlay(viewer, overlay, flip, rotation);
}
