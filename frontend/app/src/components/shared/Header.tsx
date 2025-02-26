import { Link } from "@tanstack/react-router";
import React from "react";


const Header = () => {
  return (
    <header className="bg-white shadow">
      <div className="mx-auto py-2 px-4">
        <Link to="/" className="text-xl font-bold text-gray-900">ImgQuant</Link>
      </div>
    </header>
  );
}
export default Header;