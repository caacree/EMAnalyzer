import OpenSeadragon from "openseadragon";
import { CanvasOverlay } from "@/interfaces/CanvasOverlay";

export const drawPolygonOrBboxOverlay = (viewer: OpenSeadragon.Viewer, overlay: CanvasOverlay, flip: boolean, rotation: number) => {
  const { bbox, polygon } = overlay.data || {};
  if (!bbox && !polygon) return;

  const coords = bbox || polygon;
  const tiledImage = viewer.world.getItemAt(0);
  if (!tiledImage || !coords?.length) return;

  const viewportPoints = coords.map((p: number[]) =>
    tiledImage.imageToViewportCoordinates(p[0], p[1])
  );
  const minX = Math.min(...viewportPoints.map((p: { x: number; y: number }) => p.x));
  const minY = Math.min(...viewportPoints.map((p: { x: number; y: number }) => p.y));
  const maxX = Math.max(...viewportPoints.map((p: { x: number; y: number }) => p.x));
  const maxY = Math.max(...viewportPoints.map((p: { x: number; y: number }) => p.y));

  const svgNS = "http://www.w3.org/2000/svg";
  const svgElement = document.createElementNS(svgNS, "svg");
  svgElement.setAttribute("xmlns", svgNS);
  svgElement.setAttribute(
    "style",
    "position:absolute;overflow:visible;pointer-events:none;z-index:1;width:100%;height:100%;"
  );
  svgElement.setAttribute("width", (maxX - minX).toString());
  svgElement.setAttribute("height", (maxY - minY).toString());
  svgElement.setAttribute("viewBox", `0 0 ${maxX - minX} ${maxY - minY}`);

  const polyline = document.createElementNS(svgNS, "polyline");

  // Connect all points + close the shape
  const relativePoints = viewportPoints
    .map((p: { x: number; y: number }) => `${p.x - minX},${p.y - minY}`)
    .join(" ");
  polyline.setAttribute(
    "points",
    relativePoints + ` ${viewportPoints[0].x - minX},${viewportPoints[0].y - minY}`
  );

  // fill vs. stroke
  if (overlay.fill) {
    polyline.setAttribute("fill", overlay.color || "red");
    polyline.setAttribute("stroke", "none");
  } else {
    polyline.setAttribute("fill", "none");
    polyline.setAttribute("stroke", overlay.color || "red");
    polyline.setAttribute("stroke-width", "0.01");
  }
  polyline.setAttribute("opacity", "0.5");
  svgElement.appendChild(polyline);

  // Account for flip/rotation
  const flipScale = flip ? -1 : 1;
  svgElement.style.transformOrigin = "center";
  svgElement.style.transform = `rotate(${flip ? -rotation : rotation}deg) scale(${flipScale}, 1)`;

  const wrapper = document.createElement("div");
  wrapper.appendChild(svgElement);

  viewer.addOverlay({
    id: overlay.id,
    element: wrapper as unknown as HTMLElement,
    location: new OpenSeadragon.Rect(minX, minY, maxX - minX, maxY - minY),
    checkResize: false,
    rotationMode: OpenSeadragon.OverlayRotationMode.BOUNDING_BOX
  });
};