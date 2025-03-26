import OpenSeadragon from "openseadragon";

export default function drawEphemeralStrokeInViewport(
  viewer: OpenSeadragon.Viewer,
  strokeWidth: number = 10, // e.g. 10px on screen
  imgPath: [number, number][], // [x, y] in original image coords
) {
  // If no points or a single point, remove overlay
  if (!imgPath || imgPath.length < 2) {
    viewer.removeOverlay("ephemeral-stroke");
    return;
  }

  // Get the tiledImage to perform conversions.
  const tiledImage = viewer.world.getItemAt(0);
  if (!tiledImage) return;

  // Convert each stroke point from image coordinates to viewport coordinates.
  const viewportPoints = imgPath.map(([ix, iy]) => {
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

  const polyline = document.createElementNS(svgNS, "polyline");

  // Convert stroke points to coordinates relative to the imageBounds.
  const relativePoints = viewportPoints
    .map(p => `${p.x - imageBounds.x},${p.y - imageBounds.y}`)
    .join(" ");
  polyline.setAttribute("points", relativePoints);
  polyline.setAttribute("fill", "none");
  polyline.setAttribute("stroke", "red");
  polyline.setAttribute("stroke-width", strokeWidth.toString());
  polyline.setAttribute("vector-effect", "non-scaling-stroke");

  svgEl.appendChild(polyline);

  // Wrap in a container div.
  const wrapper = document.createElement("div");
  const wrapperId = `ephemeral-stroke-${viewer.element?.id}`;
  wrapper.id = wrapperId;
  wrapper.appendChild(svgEl);

  // Remove any previous ephemeral stroke overlay and add the new one,
  // using the full image bounds as the location.
  viewer.removeOverlay(wrapperId);
  viewer.addOverlay({
    id: wrapperId,
    element: wrapper,
    location: imageBounds,
    checkResize: true,
    rotationMode: OpenSeadragon.OverlayRotationMode.BOUNDING_BOX,
  });
}
