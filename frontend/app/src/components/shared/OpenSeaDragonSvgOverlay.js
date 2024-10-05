import OpenSeadragon from 'openseadragon';

const svgNS = 'http://www.w3.org/2000/svg';

export function initSvgOverlay(viewer) {
  if (viewer._svgOverlayInfo) {
      return viewer._svgOverlayInfo;
  }

  viewer._svgOverlayInfo = new Overlay(viewer);
  return viewer._svgOverlayInfo;
}

class Overlay {
  constructor(viewer) {
    this._viewer = viewer;
    this._containerWidth = 0;
    this._containerHeight = 0;

    this._svg = document.createElementNS(svgNS, 'svg');
    this._svg.style.position = 'absolute';
    this._svg.style.left = 0;
    this._svg.style.top = 0;
    this._svg.style.width = '100%';
    this._svg.style.height = '100%';
    this._viewer.canvas.appendChild(this._svg);

    this._node = document.createElementNS(svgNS, 'g');
    this._svg.appendChild(this._node);

    this._viewer.addHandler('animation', () => {
      this.resize();
    });

    this._viewer.addHandler('open', () => {
      this.resize();
    });

    this._viewer.addHandler('rotate', () => {
      this.resize();
    });

    this._viewer.addHandler('flip', () => {
      this.resize();
    });

    this._viewer.addHandler('resize', () => {
      this.resize();
    });

    this.resize();
  }

  node() {
    return this._node;
  }

  resize() {
    if (this._containerWidth !== this._viewer.container.clientWidth) {
      this._containerWidth = this._viewer.container.clientWidth;
      this._svg.setAttribute('width', this._containerWidth);
    }

    if (this._containerHeight !== this._viewer.container.clientHeight) {
      this._containerHeight = this._viewer.container.clientHeight;
      this._svg.setAttribute('height', this._containerHeight);
    }

    const p = this._viewer.viewport.pixelFromPoint(new OpenSeadragon.Point(0, 0), true);
    const zoom = this._viewer.viewport.getZoom(true);
    const rotation = this._viewer.viewport.getRotation();
    const flipped = this._viewer.viewport.getFlip();
    const containerSizeX = this._viewer.viewport._containerInnerSize.x;
    let scaleX = containerSizeX * zoom;
    const scaleY = scaleX;

    if (flipped) {
      scaleX = -scaleX;
      p.x = -p.x + containerSizeX;
    }

    this._node.setAttribute(
      'transform',
      `translate(${p.x},${p.y}) scale(${scaleX},${scaleY}) rotate(${rotation})`
    );
  }

  onClick(node, handler) {
    new OpenSeadragon.MouseTracker({
      element: node,
      clickHandler: handler
    }).setTracking(true);
  }
}
