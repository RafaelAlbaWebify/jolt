import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { Workbench } from "./Workbench";
import "./styles.css";
import "./CompactOpportunityWorkspace.css";
import "./ApplicationWorkspace.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element was not found.");
}

createRoot(rootElement).render(
  <StrictMode>
    <Workbench />
  </StrictMode>,
);
