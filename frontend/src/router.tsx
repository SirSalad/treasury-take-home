import { createBrowserRouter } from "react-router-dom";

import { Layout } from "@/components/layout/Layout";
import { BatchPage } from "@/pages/BatchPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "batch", element: <BatchPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
