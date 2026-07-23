import { useState } from "react";
import type { FormEvent } from "react";

import {
  confirmDiscoveryRules,
  createDiscoverySession,
  sendDiscoveryMessage,
} from "./api";
import type { ProposedBusinessRule } from "./types";
import "./workflow-designer.css";

export function BusinessModelingPage() {
  const [sessionId, setSessionId] = useState("");
  const [rules, setRules] = useState<ProposedBusinessRule[]>([]);
  const [message, setMessage] = useState("");
  const [baseline, setBaseline] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const activeSession = sessionId
        ? { session_id: sessionId }
        : await createDiscoverySession("财务业务逻辑梳理");
      setSessionId(activeSession.session_id);
      const result = await sendDiscoveryMessage(activeSession.session_id, message);
      setRules((current) => [...current, ...result.proposed_rules]);
      setMessage("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "业务梳理失败");
    }
  }

  async function confirm() {
    try {
      const result = await confirmDiscoveryRules(
        sessionId,
        rules.map((rule) => rule.rule_id),
      );
      setBaseline(result.baseline.version);
      setRules((current) => current.map((rule) => ({
        ...rule,
        status: "CONFIRMED",
        executable: true,
      })));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "确认失败");
    }
  }

  return (
    <section className="workflow-page">
      <header>
        <h1>业务建模</h1>
        <p>系统只生成待确认草稿；未经财务确认的规则不会参与执行。</p>
      </header>
      {error && <div role="alert" className="error-banner">{error}</div>}
      <form className="business-discovery-form" onSubmit={submit}>
        <label>
          描述现有业务规则
          <textarea
            aria-label="业务说明"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            required
          />
        </label>
        <button type="submit">生成待确认规则</button>
      </form>
      <div className="workflow-card-list">
        {rules.map((rule) => (
          <article key={rule.rule_id} className="workflow-node-card">
            <strong>{rule.content_json.statement}</strong>
            <span>{rule.status === "CONFIRMED" ? "财务已确认" : "不可执行草稿"}</span>
            <small>建议置信度 {rule.confidence}%</small>
          </article>
        ))}
      </div>
      {rules.some((rule) => !rule.executable) && (
        <button type="button" onClick={() => void confirm()}>确认并生成业务基线</button>
      )}
      {baseline && <p role="status">业务基线版本 {baseline} 已确认</p>}
    </section>
  );
}
