/* eslint-disable no-restricted-globals */
import {
  createRootRouteWithContext,
  Outlet,
} from "@tanstack/react-router";
import React from "react";
import { Toaster } from "@/queries/toaster";
import Header from "../components/shared/Header";

const RootComponent = () => {

  return (
    <div className="bg-gray-50 w-full">
      <div
        className={`w-full min-h-screen`}
      >
        <Header />
        <Outlet />
      </div>
      <Toaster />
    </div>
  );
};

export const Route = createRootRouteWithContext()({
  component: RootComponent,
});
