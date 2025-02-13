import React from "react";
import { Link, useParams } from "@tanstack/react-router";

const CanvasMenu = () => {
  const { canvasId } = useParams({ strict: false});
  
  return (
    <div className="w-64 bg-gray-900 h-screen p-4">
      <nav className="space-y-2">
        <Link 
          to={`/canvas/${canvasId}`}
          className="block px-4 py-2 text-white hover:bg-gray-800 rounded"
        >
          Segmentations
        </Link>
        <Link 
          to={`/canvas/${canvasId}`}
          className="block px-4 py-2 text-white hover:bg-gray-800 rounded"
        >
          Correlative
        </Link>
      </nav>
    </div>
  );
};

export default CanvasMenu;
