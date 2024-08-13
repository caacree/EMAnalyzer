import "./App.css";
import './index.css'
import React from "react";

import { RouterProvider, createRouter } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Import the generated route tree
import { routeTree } from "./routeTree.gen";

// Create a new router instance
const router = createRouter({
  routeTree,
  // defaultPreload: 'intent',
  context: { auth: undefined! },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
const queryClient = new QueryClient();

const InnerApp = () => <RouterProvider router={router} />;

export const App = () => (
  <QueryClientProvider client={queryClient}>
    <InnerApp />
  </QueryClientProvider>
);

export default App;
