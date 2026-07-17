import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

import { ExportCenter } from "../ExportCenter_ds";
import { MasterDataCenter } from "../MasterDataCenter_ds";
import { TemplateStudio } from "../TemplateStudio_ds";
import { ReviewWorkbenchPage } from "../workbench/ReviewWorkbenchPage";
import { AppShell } from "./AppShell";

function ReviewRoute() {
  const navigate = useNavigate();
  const location = useLocation();
  const { formId } = useParams();
  const queue = location.pathname === "/workbench/type-confirmation"
    ? "classification"
    : location.pathname === "/workbench/recapture"
      ? "exceptions"
      : "review";
  return (
    <ReviewWorkbenchPage
      routeQueue={queue}
      routeFormId={formId}
      onQueueRouteChange={(nextQueue) => navigate(
        nextQueue === "classification" ? "/workbench/type-confirmation"
          : nextQueue === "exceptions" ? "/workbench/recapture"
            : "/workbench/review",
      )}
      onOpenTemplates={() => navigate("/templates")}
      onOpenMasterData={() => navigate("/master-data/employees")}
      onOpenExports={() => navigate("/exports")}
    />
  );
}

function TemplatesRoute() {
  const navigate = useNavigate();
  return <TemplateStudio onBack={() => navigate("/workbench/review")} />;
}

function MasterDataRoute() {
  const navigate = useNavigate();
  return <MasterDataCenter onBack={() => navigate("/workbench/review")} />;
}

function ExportsRoute() {
  const navigate = useNavigate();
  return <ExportCenter onBack={() => navigate("/workbench/review")} />;
}

function NotFound() {
  return (
    <section className="app-not-found">
      <h1>找不到这个页面</h1>
      <p>地址可能已变更，或当前模块没有这个位置。</p>
      <Link to="/workbench/review">返回审核工作台</Link>
    </section>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/workbench/review" replace />} />
        <Route path="workbench/type-confirmation" element={<ReviewRoute />} />
        <Route path="workbench/review" element={<ReviewRoute />} />
        <Route path="workbench/recapture" element={<ReviewRoute />} />
        <Route path="workbench/:formId" element={<ReviewRoute />} />
        <Route path="templates" element={<TemplatesRoute />} />
        <Route path="templates/:templateId/versions/:version" element={<TemplatesRoute />} />
        <Route path="templates/:templateId/draft" element={<TemplatesRoute />} />
        <Route path="master-data/employees" element={<MasterDataRoute />} />
        <Route path="master-data/work-orders" element={<MasterDataRoute />} />
        <Route path="master-data/products" element={<MasterDataRoute />} />
        <Route path="master-data/processes" element={<MasterDataRoute />} />
        <Route path="exports" element={<ExportsRoute />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
