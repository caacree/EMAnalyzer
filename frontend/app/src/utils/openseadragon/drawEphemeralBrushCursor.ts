import OpenSeadragon from "openseadragon";

export default function drawEphemeralBrushCursor(
  viewer: OpenSeadragon.Viewer,
  brushSize: number,
  coordinates: [number, number] | null,
) {
  if (!viewer?.element) {
    return;
  }
  
  // Get the tiledImage to perform conversions.
  const tiledImage = viewer.world.getItemAt(0);
  if (!tiledImage) return;

  // If no coordinate provided, remove the overlay.
  if (!coordinates) {
    viewer.removeOverlay(`brush-cursor-${viewer.element.id}`);
    return;
  }

  const [cx, cy] = coordinates;

  // Convert the brush center from image coordinates to viewport coordinates.
  const center = tiledImage.imageToViewportCoordinates(cx, cy);

  // Convert the brush size from pixels to viewport delta.
  // This ensures that the cursor remains a fixed size on the screen.
  const brushSizePoint = viewer.viewport.deltaPointsFromPixels(
    new OpenSeadragon.Point(brushSize, brushSize)
  );
  // For a circle, use half the converted width as the radius.
  const r = brushSizePoint.x / 2;

  // Define the bounding box of the overlay: centered at the converted coordinate.
  const minX = center.x - r;
  const minY = center.y - r;
  const width = brushSizePoint.x;
  const height = brushSizePoint.y;

  // Create an SVG element for the brush cursor.
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

  // Create a circle element at the center of the bounding box.
  const circle = document.createElementNS(svgNS, "circle");
  circle.setAttribute("cx", r.toString());
  circle.setAttribute("cy", r.toString());
  circle.setAttribute("r", r.toString());
  circle.setAttribute("fill", "none");
  circle.setAttribute("stroke", "gray");
  circle.setAttribute("stroke-width", "0.002");
  circle.setAttribute("vector-effect", "non-scaling-stroke");
  svgEl.appendChild(circle);

  // Apply rotation and flip transforms to match the stroke overlay behavior.
  const rotation = viewer.viewport.getRotation();
  const flip = viewer.viewport.getFlip();
  const flipScale = flip ? -1 : 1;
  svgEl.style.transformOrigin = "center";
  svgEl.style.transform = `rotate(${flip ? -rotation : rotation}deg) scale(${flipScale}, 1)`;

  // Wrap the SVG in a container div.
  const wrapper = document.createElement("div");
  const wrapperId = `brush-cursor-${viewer.element.id}`;
  wrapper.id = wrapperId;
  wrapper.appendChild(svgEl);
  console.log("wrapper", wrapper, center)
  // Remove any previous overlay with the same ID and add the new overlay.
  viewer.removeOverlay(wrapperId);
  viewer.addOverlay({
    id: wrapperId,
    element: wrapper,
    location: new OpenSeadragon.Rect(minX, minY, width, height),
    checkResize: false,
    rotationMode: OpenSeadragon.OverlayRotationMode.BOUNDING_BOX,
  });
}
