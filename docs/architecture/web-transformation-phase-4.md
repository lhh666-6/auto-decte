# Web 转型阶段 4：财务账本、更正和业务待办

## 已实现

- 移动电子提交在同一数据库事务内写入表单、字段、审计、回执、事实记录、财务事件和有效记录投影。
- `finance_ledger_events` 是不可变事实来源；`finance_effective_records` 是可删除、可重建的查询投影。
- 服务端 UTC 持久化，按 `Asia/Shanghai` 计算财务自然日、月和年。
- 打回生成更正记录和员工重填待办；替代提交不会覆盖原提交。
- 代填人与原填写人不同时强制填写代填原因。
- 替代记录需经财务重新审核，审核前保持 `PENDING_REVIEW`，通过后才恢复 `ACTIVE`。
- 厂长端只查询和打回本厂数据；财务端可查看全局账本及更正队列。
- 投影可由不可变事件完整重建。

## 数据不变量

1. 同一个提交的 `SUBMISSION_ACCEPTED` 事件只能写一次。
2. 一个更正根只能有一条当前有效投影。
3. 原始提交、替代提交和每次财务决定均保留事件。
4. 工厂归属由服务端身份和提交上下文确定，厂长请求不能覆盖。
5. 外部智能服务、文件解析和报表生成均不进入提交事务。

## 接口

- `GET /api/v1/finance/ledger/overview`
- `GET /api/v1/finance/ledger`
- `GET /api/v1/finance/corrections`
- `GET /api/v1/finance/business-tasks`
- `POST /api/v1/finance/corrections/{id}/replacement`
- `POST /api/v1/finance/corrections/{id}/review`
- `GET /api/v1/plant/production`
- `GET /api/v1/plant/exceptions`
- `POST /api/v1/plant/submissions/{id}/return`
