import OpenSeadragon from "openseadragon";

export default function drawEphemeralBrushCursor(
  viewer: OpenSeadragon.Viewer,
  cursor: [number, number] | null,   // viewport coords of mouse
  brushSize: number,           // in "viewport" units or your scaled logic
  flip: boolean,
  rotation: number
) {
  if (!cursor) {
    viewer.removeOverlay(`brush-cursor-${viewer.element.id}`);
    return;
  }
  const [cx, cy] = cursor;
  // We'll create a bounding box from (cx - r, cy - r) to (cx + r, cy + r).
  // Adjust how you scale brushSize from "pixels" to "viewport" if needed.
  const r = (brushSize || 10) * 0.001;  // same scaling logic as ephemeral strokes
  const minX = cx - r;
  const minY = cy - r;
  const width = 2 * r;
  const height = 2 * r;

  const svgNS = "http://www.w3.org/2000/svg";
  const svgEl = document.createElementNS(svgNS, "svg");
  svgEl.setAttribute("xmlns", svgNS);
  svgEl.setAttribute(
    "style",
    "position:absolute;overflow:visible;pointer-events:none;z-index:2;width:100%;height:100%;"
  );
  svgEl.setAttribute("width", width.toString());
  svgEl.setAttribute("height", height.toString());
  svgEl.setAttribute("viewBox", `0 0 ${width} ${height}`);

  // Create a circle in the center
  const circle = document.createElementNS(svgNS, "circle");
  circle.setAttribute("cx", r.toString());
  circle.setAttribute("cy", r.toString());
  circle.setAttribute("r", r.toString());
  circle.setAttribute("fill", "none");
  circle.setAttribute("stroke", "gray");
  circle.setAttribute("stroke-width", "0.002");
  svgEl.appendChild(circle);

  // Apply flip/rotation if needed
  const flipScale = flip ? -1 : 1;
  svgEl.style.transformOrigin = "center";
  svgEl.style.transform = `rotate(${flip ? -rotation : rotation}deg) scale(${flipScale}, 1)`;

  const wrapper = document.createElement("div");
  wrapper.id = `brush-cursor-${viewer.element.id}`;
  wrapper.appendChild(svgEl);

  viewer.removeOverlay(`brush-cursor-${viewer.element.id}`);
  viewer.addOverlay({
    element: wrapper as unknown as HTMLElement,
    location: new OpenSeadragon.Rect(minX, minY, width, height),
    checkResize: false,
    rotationMode: OpenSeadragon.OverlayRotationMode.BOUNDING_BOX
  });
}
