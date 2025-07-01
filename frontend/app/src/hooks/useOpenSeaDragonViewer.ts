// useOpenSeadragonViewer.ts
import { useEffect, useRef, useCallback, useState } from "react";
import OpenSeadragon, { TileSource, Viewer } from "openseadragon";

/* ------------ utility: stable key for deep comparison --------------- */
const keyOf = (src?: string | string[]) =>
  Array.isArray(src) ? src.join("|") : src ?? "";

interface Props {
  iiifContent?: string;
  url?: string | string[];
  positionedImages?: Array<{
    url: string;
    name: string;
    bounds: number[] | null;
  }>;
  canvasStore: any;   // Store function
  mode: "shapes" | "draw" | "navigate" | "points";
}

export function useOpenSeadragonViewer({
  iiifContent,
  url,
  positionedImages,
  mode = "navigate",
  canvasStore,
}: Props) {
  const viewerRef = useRef<HTMLDivElement>(null);
  const osdRef    = useRef<Viewer>();
  const refImgRef = useRef<OpenSeadragon.TiledImage | null>(null); // canonical
  const [isContainerReady, setIsContainerReady] = useState(false);
  const [isViewerInitialized, setIsViewerInitialized] = useState(false);
  const isDestroyedRef = useRef(false); // Add cleanup flag

  const isNav = mode === "navigate";

  // Get store state
  const storeState = canvasStore();

  // Check if container is ready
  const checkContainerReady = useCallback(() => {
    if (!viewerRef.current) return false;
    
    const rect = viewerRef.current.getBoundingClientRect();
    const isReady = rect.width > 50 && rect.height > 50; // Require larger minimum size
    
    if (isReady && !isContainerReady) {
      setIsContainerReady(true);
    } else if (!isReady && isContainerReady) {
      setIsContainerReady(false);
    }
    
    return isReady;
  }, [isContainerReady]);

  /* ------------------------------------------------------------------ 1. Monitor container size and validate sources */
  useEffect(() => {
    if (!viewerRef.current) return;

    // Initial container check
    checkContainerReady();

    // Set up resize observer
    const resizeObserver = new ResizeObserver(() => {
      checkContainerReady();
    });
    
    resizeObserver.observe(viewerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [checkContainerReady]);


  /* ------------------------------------------------------------------ 2. Initialize viewer when everything is ready */
  useEffect(() => {
    if (!isContainerReady ||  isViewerInitialized) {
      return;
    }

    const container = viewerRef.current;
    if (!container) return;

    // Double-check dimensions
    const rect = container.getBoundingClientRect();
    if (rect.width <= 50 || rect.height <= 50) {
      console.warn("Container still has insufficient dimensions, skipping initialization");
      return;
    }

    try {
      // Create a simple configuration
      const config: any = {
        element: container,
        prefixUrl: "/openseadragon/images/",
        blendTime: 0.1,
        alwaysBlend: false,
        gestureSettingsMouse: {
          clickToZoom: isNav,
          scrollToZoom: isNav,
          pinchToZoom: isNav,
          dragToPan:  isNav,
        },
        gestureSettingsTouch: {
          pinchToZoom: isNav,
          dragToPan:  isNav,
        },
        zoomPerClick:  isNav ? 2 : 1,
        zoomPerScroll: isNav ? 1.2 : 1,
        animationTime: 0,
        showNavigator: isNav,
        panHorizontal: isNav,
        panVertical:   isNav,
        showNavigationControl: isNav,
        showZoomControl:       isNav,
        crossOriginPolicy: "Anonymous",
        minZoomLevel: 0.1,
        maxZoomLevel: 100,
        visibilityRatio: 0.1,
      };

      osdRef.current = OpenSeadragon(config);

      const v = osdRef.current;

      // Debug viewport state immediately after creation

      /* ----------- zoom synchronisation (TWO-WAY) ------------------------ */
      v.addOnceHandler("open", () => {
        // reference layer will be replaced every time world is rebuilt
        refImgRef.current = v.world.getItemAt(0) ?? null;

        // Apply initial flip and rotation to the new reference
        if (refImgRef.current) {
          refImgRef.current.setFlip(storeState.flip);
          refImgRef.current.setRotation(-storeState.rotation);
        }
      });

      // Add error handler for tile loading failures
      v.addHandler("tile-load-failed", (event: any) => {
        console.warn("Tile load failed:", event);
      });

      setIsViewerInitialized(true);

    } catch (error) {
      console.error("Failed to initialize OpenSeaDragon viewer:", error);
      setIsViewerInitialized(false);
    }

    /* ----------- clean-up on unmount ----------------------------------- */
    return () => {
      isDestroyedRef.current = true;
      if (osdRef.current) {
        try {
          osdRef.current.destroy();
        } catch (error) {
          console.warn("Error destroying OpenSeaDragon viewer:", error);
        }
        osdRef.current = undefined;
      }
      setIsViewerInitialized(false);
    };
  }, [isContainerReady]);

  /* ------------------------------------------------------------------ 3. keep mode toggles in sync */
  useEffect(() => {
    const v = osdRef.current;
    if (!v || !isViewerInitialized || isDestroyedRef.current) return;

    // Use type assertion to access these properties
    const vAny = v as any;
    
    // Enable mouse events for both navigate and draw modes
    const enableMouseEvents = true;
    
    Object.assign(vAny.gestureSettingsMouse, {
      clickToZoom: isNav,
      scrollToZoom: isNav,
      pinchToZoom: isNav,
      dragToPan:   isNav,
    });
    Object.assign(vAny.gestureSettingsTouch, {
      pinchToZoom: isNav,
      dragToPan:   isNav,
    });
    vAny.zoomPerClick  = isNav ? 2 : 1;
    vAny.zoomPerScroll = isNav ? 1.2 : 1;
    vAny.panHorizontal = vAny.panVertical = isNav;
    vAny.showNavigator = isNav;
    v.setMouseNavEnabled(enableMouseEvents);
  }, [isNav, mode, isViewerInitialized]);

  /* ------------------------------------------------------------------ 4. apply flip/rotation changes */
  useEffect(() => {
    if (refImgRef.current && isViewerInitialized && !isDestroyedRef.current) {
      refImgRef.current.setFlip(storeState.flip);
      refImgRef.current.setRotation(-storeState.rotation);
    }
  }, [storeState.flip, storeState.rotation, isViewerInitialized]);

  /* ------------------------------------------------------------------ 5. rebuild WORLD when sources change */
  const srcKey = `${iiifContent ?? ""}|${keyOf(url)}|${positionedImages ? positionedImages.map(img => img.url).join("|") : ""}`;
  useEffect(() => {
    // Add a small delay to prevent rapid rebuilds
    const timeoutId = setTimeout(() => {
      const v = osdRef.current;
      if (!v || !isViewerInitialized || isDestroyedRef.current) return;

      // Ensure container still has dimensions
      const container = v.element;
      const rect = container.getBoundingClientRect();
      if (rect.width <= 50 || rect.height <= 50) {
        console.warn("Container has insufficient dimensions, skipping world rebuild");
        return;
      }

      const sources: TileSource[] = [];

      if (iiifContent) {
        sources.push({ tileSource: iiifContent } as any);
      }

      if (url) {
        const urls = Array.isArray(url) ? url : [url];
        console.log("Adding URL sources:", urls);
        urls.forEach(u => sources.push({ type: "image", url: u, buildPyramid: true } as any));
      }

      /* Remove old layers & add new ones */
      try {
        v.world.removeAll();
        refImgRef.current = null;                // reset canonical

        // If no valid sources, add a placeholder to prevent bounds issues
        if (sources.length === 0 && (!positionedImages || positionedImages.length === 0)) {
          console.warn("No valid sources found, adding placeholder image");
          // Create a 1x1 transparent pixel as a placeholder
          const canvas = document.createElement('canvas');
          canvas.width = 1;
          canvas.height = 1;
          const ctx = canvas.getContext('2d');
          if (ctx) {
            ctx.fillStyle = 'rgba(0,0,0,0)';
            ctx.fillRect(0, 0, 1, 1);
          }
          const placeholderUrl = canvas.toDataURL();
          
          v.addTiledImage({
            tileSource: { type: "image", url: placeholderUrl } as any,
            crossOriginPolicy: "Anonymous",
            success: (event: any) => {
              if (!refImgRef.current && !isDestroyedRef.current) {
                refImgRef.current = event.item;
              }
            },
            error: (event: any) => {
              console.error("Failed to load placeholder:", event);
            }
          });
          return;
        }

        // Add base layers (iiifContent and url) first
        sources.forEach((src, index) => {
          const tileSourceSpec = (src as any).tileSource ?? src; // ← unwrap once

          v.addTiledImage({
            tileSource: tileSourceSpec,
            crossOriginPolicy: "Anonymous",
            success: (event: any) => {
              if (!refImgRef.current && !isDestroyedRef.current) {
                refImgRef.current = event.item;  // first = canonical
                // Reapply rotation and flip after the new reference is set
                const currentFlip = storeState.flip;
                const currentRotation = storeState.rotation;
                event.item.setFlip(currentFlip);
                event.item.setRotation(-currentRotation);
                
                // Check the bounds of the loaded image
                const bounds = event.item.getBounds();
                
                // Check viewport bounds after image is loaded
                const viewportBounds = v.viewport.getBounds();
                
                // For the EM image (background), just let it display normally
                // Don't try to fit it to the viewport since it's the base layer
              }
            },
            error: (event: any) => {
              console.error(`Failed to load tile source ${index}:`, event);
            }
          });
        });

        // Add positioned images on top
        if (positionedImages) {
          // Wait for the base image to be loaded before adding positioned images
          const addPositionedImages = () => {
            if (v.world.getItemCount() === 0 || isDestroyedRef.current) {
              setTimeout(addPositionedImages, 100); // Retry after 100ms
              return;
            }
            
            positionedImages.forEach((positionedImage) => {
              const tileSourceSpec = { type: "image", url: positionedImage.url, buildPyramid: true } as any;
              
              const addImageOptions: any = {
                tileSource: tileSourceSpec,
                crossOriginPolicy: "Anonymous",
                error: (event: any) => {
                  console.error("Failed to load positioned image:", positionedImage.url, event);
                }
              };

              // Use x, y, width, and height parameters for positioning and sizing
              if (positionedImage.bounds) {
                const [x, y, width, height] = positionedImage.bounds;
                
                // Validate bounds to prevent zero dimensions
                if (width <= 0 || height <= 0) {
                  console.warn("Invalid bounds for positioned image:", positionedImage.name, positionedImage.bounds);
                  return;
                }
                
                // Get base image bounds for coordinate conversion
                const baseImage = v.world.getItemAt(0);
                
                if (baseImage) {
                  const baseBounds = baseImage.getBounds();
                  
                  // Validate base bounds
                  if (baseBounds.width <= 0 || baseBounds.height <= 0) {
                    console.warn("Base image has invalid bounds:", baseBounds);
                    return;
                  }
                  
                  // The base image might already be at (0,0), so we might not need to add baseBounds.x/y
                  // Let's try using just the normalized coordinates multiplied by the base image dimensions
                  const viewportX = x * baseBounds.width;
                  const viewportY = y * baseBounds.height; // No inversion needed
                  const viewportWidth = width * baseBounds.width;
                  // Note: OpenSeaDragon doesn't support both width and height, so we'll use just width
                  
                  addImageOptions.x = viewportX;
                  addImageOptions.y = viewportY;
                  addImageOptions.width = viewportWidth;
                } else {
                  // Fallback to normalized coordinates if base image not available
                  addImageOptions.x = x;
                  addImageOptions.y = y;
                  addImageOptions.width = width;
                }
              }

              v.addTiledImage(addImageOptions);
            });
          };
          
          // Start the process
          addPositionedImages();
        }
      } catch (error) {
        console.error("Error rebuilding OpenSeaDragon world:", error);
      }
    }, 50); // 50ms debounce

    return () => {
      clearTimeout(timeoutId);
    };
  }, [srcKey, positionedImages, isViewerInitialized, iiifContent, url]);

  /* ------------------------------------------------------------------ helpers */
  const setLayerOpacity = useCallback((i: number, o: number) => {
    osdRef.current?.world.getItemAt(i)?.setOpacity(o);
  }, []);

  const setLayerVisibility = useCallback(
    (i: number, visible: boolean) => setLayerOpacity(i, visible ? 1 : 0),
    [setLayerOpacity],
  );

  const getLayerCount = useCallback(
    () => osdRef.current?.world.getItemCount() ?? 0,
    [],
  );

  /* ------------------------------------------------------------------ API */
  return {
    viewerRef,
    osdViewer: osdRef.current || null,
    setLayerOpacity,
    setLayerVisibility,
    getLayerCount,
    isContainerReady,
    isViewerInitialized,
  };
}