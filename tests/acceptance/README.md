# 竹丝多身份自动诊断验收

## 目标

本目录验证：

- 多身份独立 Cookie/CSRF 会话
- 分选、浸胶、干燥、主管、厂长、财务完整链路
- 上下游表单关系
- 跨厂隔离
- 厂长 Web-only 边界
- 工资事实、日批次、月汇总和 XLSX
- 幂等键与载荷绑定
- 常用边界值

## 报告机制

每个测试场景会产生：

```text
artifacts/acceptance/<run-id>/scenarios/<test-name>/
```

失败时记录：

- 业务步骤
- 身份和渠道
- 脱敏请求/响应
- HTTP 状态和 Problem code
- Python 项目栈
- Problem code 在 `app/` 中的候选位置
- 相关数据库表现场

## 重要约定

“规范探针”依据系统不可重复写入和幂等安全原则，要求：

```text
同一个 Idempotency-Key + 相同载荷 => 返回同一结果
同一个 Idempotency-Key + 不同载荷 => 409 IDEMPOTENCY_CONFLICT
```

若当前 Bamboo 创建/阶段提交仍对不同载荷静默返回旧结果，测试会失败。这属于需要业务负责人确认的潜在缺陷。
