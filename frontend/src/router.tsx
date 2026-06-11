import { createBrowserRouter } from "react-router-dom";

import { Layout } from "@/components/layout/Layout";
import { BatchPage } from "@/pages/BatchPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { QueuePage } from "@/pages/QueuePage";
import { ReviewPage } from "@/pages/ReviewPage";
import { VerifyPage } from "@/pages/VerifyPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <QueuePage /> },
      { path: "verify", element: <VerifyPage /> },
      { path: "review/:id", element: <ReviewPage /> },
      { path: "batch", element: <BatchPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
