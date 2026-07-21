import { BrowserRouter } from "react-router-dom";

import { AppRoutes } from "./app/router";
import { PwaUpdateNotice } from "./pwa/update-notice";

export function App() {
  return (
    <BrowserRouter>
      <PwaUpdateNotice />
      <AppRoutes />
    </BrowserRouter>
  );
}
