import { useState } from "react";
import "./workspace.css";

/* ------------------------------------------------------------------ */
/*  types                                                             */
/* ------------------------------------------------------------------ */

interface AISettings {
  deepseek_enabled: boolean;
  deepseek_model: string;
  deepseek_api_endpoint: string;
  last_updated_at?: string;
}

/* ------------------------------------------------------------------ */
/*  component                                                         */
/* ------------------------------------------------------------------ */

export function AdminAISettingsPage() {
  const [settings] = useState<AISettings>({
    deepseek_enabled: false,
    deepseek_model: "deepseek-chat",
    deepseek_api_endpoint: "https://api.deepseek.com/v1",
    last_updated_at: undefined,
  });

  return (
    <section className="ai-settings-page">
      <header className="ai-settings-header">
        <div>
          <h1>AI 辅助设置</h1>
          <p>管理 DeepSeek 等 AI 模型的接入配置与状态。</p>
        </div>
      </header>

      <div className="ai-settings-card">
        <div className="ai-status-row">
          <div className="ai-status-indicator">
            <span
              className={`ai-status-dot ${settings.deepseek_enabled ? "ai-status-on" : "ai-status-off"}`}
              aria-hidden="true"
            />
            <span className="ai-status-label">DeepSeek 配置状态</span>
          </div>
          <span className={`ai-status-text ${settings.deepseek_enabled ? "ai-text-on" : "ai-text-off"}`}>
            {settings.deepseek_enabled ? "已启用" : "未启用"}
          </span>
        </div>

        <div className="ai-settings-detail">
          <div className="ai-settings-field">
            <span className="ai-field-label">模型</span>
            <span className="ai-field-value">{settings.deepseek_model}</span>
          </div>
          <div className="ai-settings-field">
            <span className="ai-field-label">API 端点</span>
            <span className="ai-field-value">{settings.deepseek_api_endpoint}</span>
          </div>
          {settings.last_updated_at && (
            <div className="ai-settings-field">
              <span className="ai-field-label">最后更新</span>
              <span className="ai-field-value">
                {new Date(settings.last_updated_at).toLocaleString("zh-CN")}
              </span>
            </div>
          )}
        </div>

        <div className="ai-disabled-notice">
          <p className="ai-notice-icon" aria-hidden="true">&#9888;</p>
          <div>
            <strong>AI 辅助功能当前未启用</strong>
            <p>
              DeepSeek 模型未配置或已被管理员关闭。启用后可用于业务规则发现、异常模式分析等辅助功能。
              如需启用，请联系系统管理员配置 API 密钥并开启服务。
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
