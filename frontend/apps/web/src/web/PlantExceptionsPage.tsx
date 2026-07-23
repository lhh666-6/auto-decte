import { useEffect, useState } from "react";

import { getPlantExceptions } from "./api";
import type { BusinessTask, SubmissionCorrection } from "./types";
import "./ledger-pages.css";

export function PlantExceptionsPage() {
  const [corrections, setCorrections] = useState<SubmissionCorrection[]>([]);
  const [tasks, setTasks] = useState<BusinessTask[]>([]);
  useEffect(() => {
    void getPlantExceptions().then((result) => {
      setCorrections(result.corrections);
      setTasks(result.tasks);
    });
  }, []);
  return (
    <section className="ledger-page">
      <header><h1>本厂异常与待办</h1><p>更正、代填、复核均保留处理人和状态。</p></header>
      <h2>更正记录</h2>
      <div className="ledger-case-list">
        {corrections.map((item) => (
          <article key={item.correction_id}>
            <strong>{item.original_submission_id} · {item.status}</strong>
            <span>{item.reason}</span>
          </article>
        ))}
      </div>
      <h2>业务待办</h2>
      <div className="ledger-case-list">
        {tasks.map((task) => (
          <article key={task.task_id}>
            <strong>{task.task_type} · {task.status}</strong>
            <span>处理人：{task.assigned_to}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
