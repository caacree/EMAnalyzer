import OpenSeadragon from "openseadragon";
import { CanvasOverlay } from "@/interfaces/CanvasOverlay"; // your shared interfaces

export function drawBrushStrokeOverlay(
  viewer: OpenSeadragon.Viewer,
  overlay: CanvasOverlay,
  flip: boolean,
  rotation: number
) {
  const { path } = overlay.data;
    if (!path || path.length < 2) return; // need at least 2 points
    const tiledImage = viewer.world.getItemAt(0);
    if (!tiledImage) return;

    const viewportPoints = path.map((p: number[]) =>
      tiledImage.imageToViewportCoordinates(p[0], p[1])
    );

    const minX = Math.min(...viewportPoints.map((p: { x: number; y: number }) => p.x));
    const minY = Math.min(...viewportPoints.map((p: { x: number; y: number }) => p.y));
    const maxX = Math.max(...viewportPoints.map((p: { x: number; y: number }) => p.x));
    const maxY = Math.max(...viewportPoints.map((p: { x: number; y: number }) => p.y));

    const width = maxX - minX || 0.00001;
    const height = maxY - minY || 0.00001;

    const svgNS = "http://www.w3.org/2000/svg";
    const svgElement = document.createElementNS(svgNS, "svg");
    svgElement.setAttribute("xmlns", svgNS);
    svgElement.setAttribute(
      "style",
      "position:absolute;overflow:visible;pointer-events:none;z-index:2;width:100%;height:100%;"
    );
    svgElement.setAttribute("width", width.toString());
    svgElement.setAttribute("height", height.toString());
    svgElement.setAttribute("viewBox", `0 0 ${width} ${height}`);

    // Build the polyline
    const polylinePoints = viewportPoints
      .map((p: { x: number; y: number }) => `${p.x - minX},${p.y - minY}`)
      .join(" ");
    const polyline = document.createElementNS(svgNS, "polyline");
    polyline.setAttribute("points", polylinePoints);

    polyline.setAttribute("fill", "none");
    polyline.setAttribute("stroke", overlay.color || "red");
    // Make sure the brush stroke is visible
    // We'll scale the stroke width by ~0.001 for OSD's coordinate space
    const strokePx = (overlay.strokeWidth || 10) * 0.001;
    polyline.setAttribute("stroke-width", strokePx.toString());
    polyline.setAttribute("stroke-linecap", "round");
    polyline.setAttribute("stroke-linejoin", "round");

    svgElement.appendChild(polyline);

    // Flip/rotate
    const flipScale = flip ? -1 : 1;
    svgElement.style.transformOrigin = "center";
    svgElement.style.transform = `rotate(${flip ? -rotation : rotation}deg) scale(${flipScale}, 1)`;

    const wrapper = document.createElement("div");
    wrapper.appendChild(svgElement);

    viewer.addOverlay({
      id: overlay.id,
      element: wrapper as unknown as HTMLElement,
      location: new OpenSeadragon.Rect(minX, minY, width, height),
      checkResize: false,
      rotationMode: OpenSeadragon.OverlayRotationMode.BOUNDING_BOX
    });
  }