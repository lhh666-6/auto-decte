import type { ReactNode } from "react";

export interface DiffField {
  key: string;
  label: string;
  type: string;
  oldValue?: string;
  newValue?: string;
  change: "added" | "removed" | "modified" | "unchanged";
}

export interface DiffNode {
  id: string;
  label: string;
  type: string;
  change: "added" | "removed" | "modified" | "unchanged";
  details?: string;
}

export interface DiffRuleLine {
  key: string;
  oldValue: string;
  newValue: string;
}

export interface VersionDiffPanelProps {
  title: string;
  fields?: DiffField[];
  nodes?: DiffNode[];
  ruleLines?: DiffRuleLine[];
  emptyMessage?: string;
  /** When true, signals this is the first version with nothing to diff against. */
  isFirstVersion?: boolean;
}

function ChangeBadge({ change }: { change: DiffField["change"] | DiffNode["change"] }) {
  const labels: Record<string, string> = {
    added: "新增",
    removed: "删除",
    modified: "已修改",
    unchanged: "未变更",
  };
  return (
    <span className={`diff-change-badge diff-change-${change}`}>
      {labels[change] ?? change}
    </span>
  );
}

export function VersionDiffPanel({
  title,
  fields,
  nodes,
  ruleLines,
  emptyMessage = "无变更记录",
  isFirstVersion = false,
}: VersionDiffPanelProps) {
  let body: ReactNode;

  if (isFirstVersion) {
    body = <p className="diff-first-version">首次版本，没有上一版本可对比</p>;
  } else if (fields && fields.length > 0) {
    body = (
      <table className="diff-table">
        <thead>
          <tr>
            <th>字段标识</th>
            <th>名称</th>
            <th>类型</th>
            <th>原值</th>
            <th>新值</th>
            <th>变更</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => (
            <tr key={field.key}>
              <td>{field.key}</td>
              <td>{field.label}</td>
              <td>{field.type}</td>
              <td>{field.oldValue ?? "-"}</td>
              <td>{field.newValue ?? "-"}</td>
              <td><ChangeBadge change={field.change} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  } else if (nodes && nodes.length > 0) {
    body = (
      <table className="diff-table">
        <thead>
          <tr>
            <th>节点 ID</th>
            <th>名称</th>
            <th>类型</th>
            <th>详情</th>
            <th>变更</th>
          </tr>
        </thead>
        <tbody>
          {nodes.map((node) => (
            <tr key={node.id}>
              <td>{node.id}</td>
              <td>{node.label}</td>
              <td>{node.type}</td>
              <td>{node.details ?? "-"}</td>
              <td><ChangeBadge change={node.change} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  } else if (ruleLines && ruleLines.length > 0) {
    body = (
      <table className="diff-table">
        <thead>
          <tr>
            <th>参数</th>
            <th>原值</th>
            <th>新值</th>
          </tr>
        </thead>
        <tbody>
          {ruleLines.map((line) => (
            <tr key={line.key}>
              <td>{line.key}</td>
              <td>{line.oldValue}</td>
              <td>{line.newValue}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  } else {
    body = <p className="diff-empty">{emptyMessage}</p>;
  }

  return (
    <div className="version-diff-panel">
      <h3 className="diff-panel-title">{title}</h3>
      {body}
    </div>
  );
}
