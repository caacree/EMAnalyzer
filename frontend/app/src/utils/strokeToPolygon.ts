// strokePathToPolygon.ts
import getStroke from 'perfect-freehand';

/**
 * Convert a polyline (the user's freehand path) into a filled polygon
 * with thickness = brushWidth. We rely on the perfect-freehand library.
 */
export function strokePathToPolygon(path: [number, number, number][], brushWidth: number) {
  if (!path ) {
    return [];
  }
  // Perfect Freehand options (tweak to taste):
  const options = {
    size: brushWidth,         // "diameter" of the stroke in the same units as the path
    thinning: 0,              // No tapering from pressure
    smoothing: 0,           // Adjust smoothing if you like
    streamline: 0,          // Additional smoothing on the input points
    simulatePressure: false,  // The stroke won't vary in width based on "pressure"
    // ...lots more in the docs: https://github.com/tldraw/perfect-freehand
  };

  let strokePoints = [];
  if (path.length < 2) {
    // This is a single point, so should be a circle with radius of the 1/2 brush width
    const radius = brushWidth / 2;
    strokePoints = getStroke([[path[0][0] - radius, path[0][1] - radius], [path[0][0] + radius, path[0][1] + radius]], options);
  } else {
    // Get the polygon describing the stroke outline.
    // This returns an array of [x, y] points in the same coordinate space as `path`.
    strokePoints = getStroke(path, options);
  }

  // perfect-freehand does NOT automatically "close" the shape, because it’s used
  // for rendering. However, for a filled polygon overlay, we typically want to close it:
  // Make sure the polygon loops back to the first point:
  if (strokePoints.length > 0) {
    strokePoints.push(strokePoints[0]);
  }

  return strokePoints;
}
