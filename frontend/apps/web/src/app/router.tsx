import {
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";

import type { MasterDataCatalog } from "@form-detection/api-client";

import { ExportCenter } from "../ExportCenter_ds";
import { MasterDataCenter } from "../MasterDataCenter_ds";
import { TemplateStudio } from "../TemplateStudio_ds";
import { ReviewWorkbenchPage } from "../workbench/ReviewWorkbenchPage";
import { MobileV3Shell } from "../mobile/v3/MobileV3Shell";
import { BambooV3HomePage } from "../mobile/v3/BambooV3HomePage";
import { MobileLoginPage } from "../mobile/MobileLoginPage";
import { MobileBambooProcessPage } from "../mobile/MobileBambooProcessPage";
import { BambooV3SubmissionsPage } from "../mobile/v3/BambooV3SubmissionsPage";
import { BambooV3ProfilePage } from "../mobile/v3/BambooV3ProfilePage";
import { BambooPersonnelPage } from "../mobile/personnel/BambooPersonnelPage";
import { MobileSessionProvider } from "../mobile/session/MobileSessionProvider";
import { RequireMobileSession } from "../mobile/session/RequireMobileSession";
import { RequireWebSession } from "../web/RequireWebSession";
import { AdminFormApprovalsPage } from "../web/AdminFormApprovalsPage";
import { AdminWorkflowApprovalsPage } from "../web/AdminWorkflowApprovalsPage";
import { BusinessModelingPage } from "../web/BusinessModelingPage";
import { FinanceFormsPage } from "../web/FinanceFormsPage";
import { FinanceLedgerPage } from "../web/FinanceLedgerPage";
import { PlantExceptionsPage } from "../web/PlantExceptionsPage";
import { PlantFormsPage } from "../web/PlantFormsPage";
import { PlantNotificationsPage } from "../web/PlantNotificationsPage";
import { PlantProductionPage } from "../web/PlantProductionPage";
import { PlantWorkflowsPage } from "../web/PlantWorkflowsPage";
import { WorkflowDesignerPage } from "../web/WorkflowDesignerPage";
import { WebLoginPage } from "../web/WebLoginPage";
import {
  WebSessionProvider,
  useWebSession,
} from "../web/WebSessionProvider";
import { WorkspaceOverviewPage } from "../web/WorkspaceOverviewPage";
import { WorkspaceShell } from "../web/WorkspaceShell";
import type { WorkspaceRole } from "../web/types";
import { AppShell } from "./AppShell";

function WebSessionLayout() {
  return (
    <WebSessionProvider>
      <Outlet />
    </WebSessionProvider>
  );
}

function WebRoot() {
  const { status, session } = useWebSession();
  if (status === "loading") return <div role="status">正在验证登录状态…</div>;
  return <Navigate to={session?.landing_path ?? "/login"} replace />;
}

function WebWorkspaceLayout({ workspace }: { workspace: WorkspaceRole }) {
  return (
    <RequireWebSession workspace={workspace}>
      <WorkspaceShell workspace={workspace}>
        <Outlet />
      </WorkspaceShell>
    </RequireWebSession>
  );
}

function WorkspaceComingSoon() {
  return (
    <section>
      <h1>功能建设中</h1>
      <p>该模块将在后续开发阶段接入。</p>
    </section>
  );
}

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
    />
  );
}

function TemplatesRoute() {
  const navigate = useNavigate();
  const location = useLocation();
  const { templateId, version } = useParams();
  const initialScreen = version
    ? { kind: "preview" as const, versionId: version }
    : location.pathname.endsWith("/draft") && templateId
      ? { kind: "editor" as const, versionId: templateId }
      : { kind: "library" as const };
  return (
    <TemplateStudio
      initialScreen={initialScreen}
      onScreenChange={(screen) => {
        if (screen.kind === "library") navigate("/templates");
        else if (screen.kind === "preview") navigate(`/templates/${screen.versionId}/versions/${screen.versionId}`);
        else navigate(`/templates/${screen.versionId}/draft`);
      }}
    />
  );
}

function MasterDataRoute() {
  const navigate = useNavigate();
  const location = useLocation();
  const segment = location.pathname.split("/").at(-1);
  const catalog = (["employees", "work-orders", "products", "processes"] as const).includes(
    segment as MasterDataCatalog,
  ) ? segment as MasterDataCatalog : "employees";
  return (
    <MasterDataCenter
      initialCatalog={catalog}
      onCatalogChange={(nextCatalog) => navigate(`/master-data/${nextCatalog}`)}
    />
  );
}

function ExportsRoute() {
  return <ExportCenter />;
}

function LegacyBambooRecordRedirect() {
  const { recordId } = useParams<{ recordId: string }>();
  return <Navigate to={`/mobile/records/${encodeURIComponent(recordId ?? "")}`} replace />;
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
      {/* Unified desktop management entry and role workspaces. */}
      <Route element={<WebSessionLayout />}>
        <Route index element={<WebRoot />} />
        <Route path="login" element={<WebLoginPage />} />

        <Route path="finance" element={<WebWorkspaceLayout workspace="FINANCE" />}>
          <Route index element={<Navigate to="/finance/overview" replace />} />
          <Route path="overview" element={<WorkspaceOverviewPage workspace="FINANCE" />} />
          <Route path="forms" element={<FinanceFormsPage />} />
          <Route path="workflows" element={<WorkflowDesignerPage />} />
          <Route path="business-modeling" element={<BusinessModelingPage />} />
          <Route path="today" element={<FinanceLedgerPage />} />
          <Route path="month" element={<FinanceLedgerPage />} />
          <Route path="year" element={<FinanceLedgerPage />} />
          <Route path="exceptions" element={<FinanceLedgerPage />} />
          <Route path="*" element={<WorkspaceComingSoon />} />
        </Route>

        <Route path="admin" element={<WebWorkspaceLayout workspace="ADMIN" />}>
          <Route index element={<Navigate to="/admin/overview" replace />} />
          <Route path="overview" element={<WorkspaceOverviewPage workspace="ADMIN" />} />
          <Route path="form-approvals" element={<AdminFormApprovalsPage />} />
          <Route path="workflow-approvals" element={<AdminWorkflowApprovalsPage />} />
          <Route path="*" element={<WorkspaceComingSoon />} />
        </Route>

        <Route path="plant" element={<WebWorkspaceLayout workspace="PLANT_MANAGER" />}>
          <Route index element={<Navigate to="/plant/overview" replace />} />
          <Route path="overview" element={<WorkspaceOverviewPage workspace="PLANT_MANAGER" />} />
          <Route path="notifications" element={<PlantNotificationsPage />} />
          <Route path="forms" element={<PlantFormsPage />} />
          <Route path="workflows" element={<PlantWorkflowsPage />} />
          <Route path="production" element={<PlantProductionPage />} />
          <Route path="exceptions" element={<PlantExceptionsPage />} />
          <Route path="*" element={<WorkspaceComingSoon />} />
        </Route>
      </Route>

      {/* Desktop routes */}
      <Route element={<AppShell />}>
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

      {/* Mobile routes — separate layout with bottom tab nav */}
      <Route element={<MobileSessionProvider><MobileV3Shell /></MobileSessionProvider>}>
        <Route path="mobile" element={<Navigate to="/mobile/home" replace />} />
        <Route path="mobile/login" element={<MobileLoginPage />} />
        <Route path="mobile/record" element={<Navigate to="/mobile/work" replace />} />
        <Route path="mobile/record/bamboo-process" element={<Navigate to="/mobile/work" replace />} />
        <Route path="mobile/record/bamboo-process/:recordId" element={<LegacyBambooRecordRedirect />} />
        <Route path="mobile/drafts" element={<Navigate to="/mobile/submissions" replace />} />
        <Route path="mobile/outbox" element={<Navigate to="/mobile/submissions" replace />} />
        <Route element={<RequireMobileSession />}>
          <Route path="mobile/home" element={<BambooV3HomePage />} />
          <Route path="mobile/work" element={<MobileBambooProcessPage />} />
          <Route path="mobile/records/:recordId" element={<MobileBambooProcessPage />} />
          <Route path="mobile/record/sheet-piece" element={<Navigate to="/mobile/work" replace />} />
          <Route path="mobile/record/team-sheet-piece" element={<Navigate to="/mobile/work" replace />} />
          <Route path="mobile/submissions" element={<BambooV3SubmissionsPage />} />
          <Route path="mobile/profile" element={<BambooV3ProfilePage />} />
          <Route path="mobile/personnel" element={<BambooPersonnelPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
