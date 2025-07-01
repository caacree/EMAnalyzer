import OpenSeadragon from "openseadragon";
import { CanvasOverlay } from "@/interfaces/CanvasOverlay";

export const drawPolygonOrBboxOverlay = (viewer: OpenSeadragon.Viewer, overlay: CanvasOverlay) => {
  const { bbox, polygon } = overlay.data || {};
  if (!bbox && !polygon) return;

  const coords = bbox || polygon;
  const tiledImage = viewer.world.getItemAt(0);
  if (!tiledImage || !coords?.length) return;
  
  const flip = tiledImage.getFlip();
  const contentSize = tiledImage.getContentSize();
  const viewportPoints = coords.map(([ix, iy]: [number, number]) => {
    if (flip) {
      ix = contentSize.x - ix;
    }
    const { x, y } = tiledImage.imageToViewportCoordinates(ix, iy);
    return { x, y };
  });

  // Use the full image bounds as the fixed coordinate system.
  const imageBounds = tiledImage.getBounds(); // OpenSeadragon.Rect with x, y, width, height

  // Create an SVG element that spans the entire image
  const svgNS = "http://www.w3.org/2000/svg";
  const svgEl = document.createElementNS(svgNS, "svg");
  svgEl.setAttribute("xmlns", svgNS);
  svgEl.setAttribute("width", imageBounds.width.toString());
  svgEl.setAttribute("height", imageBounds.height.toString());
  svgEl.setAttribute("viewBox", `0 0 ${imageBounds.width} ${imageBounds.height}`);
  svgEl.setAttribute(
    "style",
    "position:absolute;overflow:visible;pointer-events:none;z-index:1;width:100%;height:100%;"
  );
  svgEl.setAttribute("pointer-events", "none");
  const polyline = document.createElementNS(svgNS, "polyline");

  // Connect all points + close the shape
  const relativePoints = viewportPoints
    .map(p => `${p.x - imageBounds.x},${p.y - imageBounds.y}`)
    .join(" ") + ` ${viewportPoints[0].x - imageBounds.x},${viewportPoints[0].y - imageBounds.y}`;
  polyline.setAttribute(
    "points",
    relativePoints
  );

  // fill vs. stroke
  if (overlay.fill && !bbox) {
    polyline.setAttribute("fill", overlay.color || "red");
    polyline.setAttribute("stroke", "none");
  } else {
    polyline.setAttribute("fill", "none");
    polyline.setAttribute("stroke", overlay.color || "red");
    polyline.setAttribute("stroke-width", "0.01");
  }
  polyline.setAttribute("opacity", "0.5");
  svgEl.appendChild(polyline);

  const wrapper = document.createElement("div");
  wrapper.id = overlay.id;
  wrapper.appendChild(svgEl);

  viewer.removeOverlay(overlay.id);
  viewer.addOverlay({
    id: overlay.id,
    element: wrapper as unknown as HTMLElement,
    location: imageBounds,
    checkResize: true,
    rotationMode: OpenSeadragon.OverlayRotationMode.BOUNDING_BOX
  });
};