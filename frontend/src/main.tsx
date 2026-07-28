import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./ApplicationOverviewAutoExpand";
import { Workbench } from "./Workbench";
import "./styles.css";
import "./CompactOpportunityWorkspace.css";
import "./CompactInspectorOverrides.css";
import "./ApplicationWorkspace.css";
import "./ApplicationPipelineBoard.css";
import "./ApplicationWorkItems.css";
import "./OpportunityApplicationHandoff.css";
import "./MarketIntelligence.css";
import "./ProfessionalIntelligence.css";
import "./ProfessionalStructuredExtraction.css";
import "./WorkflowRefinement.css";
import "./ReleaseBlockingUx.css";
import "./RuntimeIdentity.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element was not found.");
}

createRoot(rootElement).render(
  <StrictMode>
    <Workbench />
  </StrictMode>,
);
