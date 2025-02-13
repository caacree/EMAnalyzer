import React from "react";
import { Link, useParams } from "@tanstack/react-router";

const CanvasMenu = () => {
  const { canvasId } = useParams();
  
  return (
    <div className="w-64 bg-gray-100 h-screen p-4">
      <nav className="space-y-2">
        <Link 
          to={`/canvas/${canvasId}`}
          className="block px-4 py-2 text-gray-700 hover:bg-gray-200 rounded"
        >
          Segmentations
        </Link>
        <Link 
          to={`/canvas/${canvasId}`}
          className="block px-4 py-2 text-gray-700 hover:bg-gray-200 rounded"
        >
          Correlative
        </Link>
      </nav>
    </div>
  );
};

export default CanvasMenu;
