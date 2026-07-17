import { useState } from "react";

import { ExportCenter } from "./ExportCenter_ds";
import { MasterDataCenter } from "./MasterDataCenter_ds";
import { TemplateStudio } from "./TemplateStudio_ds";
import { ReviewWorkbenchPage } from "./workbench/ReviewWorkbenchPage";

type Feature = "review" | "templates" | "master-data" | "exports";

export function App() {
  const [feature, setFeature] = useState<Feature>("review");

  return (
    <>
      <div hidden={feature !== "review"}>
        <ReviewWorkbenchPage
          onOpenTemplates={() => setFeature("templates")}
          onOpenMasterData={() => setFeature("master-data")}
          onOpenExports={() => setFeature("exports")}
        />
      </div>
      {feature === "templates" && (
        <TemplateStudio onBack={() => setFeature("review")} />
      )}
      {feature === "master-data" && (
        <MasterDataCenter onBack={() => setFeature("review")} />
      )}
      {feature === "exports" && (
        <ExportCenter onBack={() => setFeature("review")} />
      )}
    </>
  );
}
