import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { MobileApiError } from "@form-detection/api-client";

import { useMobileSession } from "../session/MobileSessionProvider";
import { usePwaInstall } from "../pwa/usePwaInstall";
import {
  getBambooNotificationPreference,
  requestBambooNotificationPermission,
  type BambooNotificationPreference,
} from "../notifications/system-notifications";
import { getPendingLogoutCount } from "../storage/session-cleanup";

const ROLE_LABELS: Record<string, string> = {
  SORT_OPERATOR: "分选工",
  DIPPING_OPERATOR: "浸胶工",
  DRYING_RACK_OPERATOR: "干燥工",
  INSPECTOR: "检测人",
  SUPERVISOR: "主管",
  PLANT_MANAGER: "厂长",
  FINANCE_APPROVER: "财务",
  SYSTEM_ADMIN: "管理员",
};

export function BambooV3ProfilePage() {
  const navigate = useNavigate();
  const { sessionMetadata: profile, logout } = useMobileSession();
  const pwa = usePwaInstall();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [notificationPreference, setNotificationPreference] = useState<BambooNotificationPreference>("disabled");

  useEffect(() => {
    if (profile) setNotificationPreference(getBambooNotificationPreference(profile.employee_code));
  }, [profile]);

  if (!profile) return null;
  const role = profile.bamboo_role ?? "";

  const handleLogout = async () => {
    const pending = await getPendingLogoutCount();
    if (pending > 0 && !window.confirm(`本机还有 ${pending} 条未同步记录，确认退出吗？`)) return;
    setBusy(true);
    try {
      await logout();
      navigate("/mobile/login", { replace: true });
    } catch (cause) {
      setMessage(cause instanceof MobileApiError ? cause.problem.detail : "退出失败，请重试");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mobile-page bamboo-v3-page bamboo-v3-profile">
      <header className="bamboo-v3-page-header"><p>账号、班组与应用状态</p><h2>我的</h2></header>
      <section className="bamboo-v3-profile-card">
        <div className="bamboo-v3-avatar" aria-hidden="true">{profile.employee_name.charAt(0)}</div>
        <div><strong>{profile.employee_name}</strong><span>{profile.employee_code} · {profile.team_name}</span></div>
      </section>
      {message && <div className="mobile-status-banner" role="status">{message}</div>}
      <dl className="bamboo-v3-settings-card">
        <div><dt>所属工厂</dt><dd>{profile.factory_name || "待分配"}</dd></div>
        <div><dt>当前职务</dt><dd>{ROLE_LABELS[role] || profile.position || "待分配"}</dd></div>
        <div><dt>网络状态</dt><dd>{navigator.onLine ? "联网" : "离线"}</dd></div>
        <div><dt>应用版本</dt><dd>V3</dd></div>
      </dl>
      <section className="bamboo-v3-profile-actions">
        {["PLANT_MANAGER", "SYSTEM_ADMIN"].includes(role) && (
          <button type="button" onClick={() => navigate("/mobile/personnel")}>人员调度中心</button>
        )}
        {role === "FINANCE_APPROVER" && <a href="/">财务工作请前往网页端</a>}
        <button type="button" disabled={notificationPreference !== "disabled"} onClick={() => void requestBambooNotificationPermission(profile.employee_code).then((preference) => {
          setNotificationPreference(preference);
          if (preference === "enabled") setMessage("消息弹窗已开启；消息中心仍会永久保存记录。");
          else if (preference === "denied") setMessage("浏览器已拒绝通知，可在 Chrome 网站设置中重新允许。");
          else if (preference === "unsupported") setMessage("当前浏览器不支持系统消息弹窗。");
        })}>{notificationButtonLabel(notificationPreference)}</button>
        <button type="button" disabled={pwa.installed} onClick={() => void pwa.install().then((result) => {
          if (result === "unavailable") setMessage("当前没有直接安装提示，请点 Chrome 右上角菜单 → 安装应用/添加到主屏幕。");
          else if (result === "dismissed") setMessage("已取消安装，稍后仍可再次添加到桌面。");
          else setMessage("已添加到桌面，可像普通应用一样打开。");
        })}>{pwa.installed ? "已安装到桌面" : "一键添加到桌面"}</button>
        <button type="button" className="danger" disabled={busy} onClick={() => void handleLogout()}>退出登录</button>
      </section>
      <p className="bamboo-v3-empty-copy">岗位调动需线下联系厂长，由厂长在人员调度中心提交；员工端不提供自行申请入口。</p>
    </div>
  );
}

function notificationButtonLabel(preference: BambooNotificationPreference): string {
  return ({
    disabled: "开启消息弹窗",
    enabled: "消息弹窗已开启",
    denied: "浏览器已拒绝通知",
    unsupported: "浏览器不支持消息弹窗",
  })[preference];
}
