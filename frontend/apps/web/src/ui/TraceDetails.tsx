import { useState } from "react";

export interface TraceItem {
  label: string;
  value: string;
}

export function TraceDetails({
  items,
  summary = "追溯详情",
  copyLabel = "复制追溯信息",
  defaultOpen = false,
}: {
  items: TraceItem[];
  summary?: string;
  copyLabel?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  async function copy() {
    const content = items.map((item) => `${item.label}: ${item.value}`).join("\n");
    await navigator.clipboard?.writeText(content);
  }

  return (
    <details className="trace-details" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>{summary}</summary>
      {open ? (
        <div className="trace-details-content">
          <dl>
            {items.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
          </dl>
          <button type="button" className="text-button" onClick={() => void copy()}>{copyLabel}</button>
        </div>
      ) : null}
    </details>
  );
}
