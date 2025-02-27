import OpenSeadragon from "openseadragon";

export default function drawEphemeralStrokeInViewport(
  viewer: OpenSeadragon.Viewer,
  vpPath: [number, number][],
  strokeWidth: number
) {
  console.log("drawing stroke", vpPath, strokeWidth);
  if (vpPath.length < 2) return;

  // Find bounding box in viewport coordinates
  const minX = Math.min(...vpPath.map(p => p[0]));
  const minY = Math.min(...vpPath.map(p => p[1]));
  const maxX = Math.max(...vpPath.map(p => p[0]));
  const maxY = Math.max(...vpPath.map(p => p[1]));

  const width = Math.max(maxX - minX, 0.00001);
  const height = Math.max(maxY - minY, 0.00001);

  // Create an <svg> in that viewport bounding rect
  const svgNS = "http://www.w3.org/2000/svg";
  const svgEl = document.createElementNS(svgNS, "svg");
  svgEl.setAttribute("width", width.toString());
  svgEl.setAttribute("height", height.toString());
  svgEl.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svgEl.style.position = "absolute";
  svgEl.style.overflow = "visible";
  svgEl.style.pointerEvents = "none";
  svgEl.style.zIndex = "999"; // so it appears on top

  // Build a polyline
  const polylinePoints = vpPath
    .map(([vx, vy]) => `${vx - minX},${vy - minY}`)
    .join(" ");

  const polyline = document.createElementNS(svgNS, "polyline");
  polyline.setAttribute("points", polylinePoints);
  polyline.setAttribute("fill", "none");
  polyline.setAttribute("stroke", "red");
  polyline.setAttribute("stroke-width", strokeWidth.toString());
  polyline.setAttribute("stroke-linecap", "round");
  polyline.setAttribute("stroke-linejoin", "round");
  svgEl.appendChild(polyline);

  const wrapper = document.createElement("div");
  wrapper.appendChild(svgEl);

  // Now add this ephemeral overlay in *viewport* coordinates
  viewer.addOverlay({
    element: wrapper as unknown as HTMLElement,
    location: new OpenSeadragon.Rect(minX, minY, width, height),
    checkResize: false,
    rotationMode: OpenSeadragon.OverlayRotationMode.EXACT
  });
}