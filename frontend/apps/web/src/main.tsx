import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* App owns the browser router so component tests and production share one entry. */}
    <App />
  </StrictMode>,
);
