// types/openseadragon-filtering.d.ts
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import OpenSeadragon from 'openseadragon';

declare global {
  namespace OpenSeadragon {
    interface Viewer {
      setFilterOptions(options: {
        filters?: {
          items?: OpenSeadragon.TiledImage | OpenSeadragon.TiledImage[];
          processors: FilterProcessor | FilterProcessor[];
        };
        loadMode?: 'sync' | 'async';
      }): void;
    }

    namespace Filters {
      function THRESHOLDING(threshold: number): FilterProcessor;
      function BRIGHTNESS(adjustment: number): FilterProcessor;
      function CONTRAST(adjustment: number): FilterProcessor;
      function GAMMA(adjustment: number): FilterProcessor;
      function GREYSCALE(): FilterProcessor;
      function INVERT(): FilterProcessor;
      function MORPHOLOGICAL_OPERATION(kernelSize: number, comparator: (a: number, b: number) => number): FilterProcessor;
      function CONVOLUTION(kernel: number[]): FilterProcessor;
      function COLORMAP(cmap: number[][], ctr: number): FilterProcessor;
    }
  }

  type FilterProcessor = (context: CanvasRenderingContext2D, callback: () => void) => void;
}

declare module 'openseadragon-filtering' {
  export {};
}

export {};