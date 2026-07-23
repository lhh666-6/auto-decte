# Web 转型阶段 5：工资规则与历史重算

## 已实现

- 财务创建按工厂、岗位配置的版本化工资规则草稿。
- 工资 DSL 只允许“计量字段 × 单价 + 基础金额”，不执行任意代码。
- 管理员是规则生效和失效的唯一批准角色；新版本生效时旧版本退役。
- 每个计算批次冻结规则版本、日期范围、工厂和财务事件数据水位。
- 计算结果不可变；未经过财务二次确认不会进入正式工资查询。
- 管理员可基于已确认批次发起历史重算，保存原金额、新金额和差额。
- 重算确认前旧正式工资保持不变；确认后旧批次标记为已被替代，但旧结果不删除。
- 财务查看全局、管理员查看全局、厂长只查看本厂；每次正式工资查询写访问审计。
- 原移动端工资事实继续遵守普通员工仅看本人、厂长本厂、财务和管理员全局的既有策略。

## 关键接口

- `GET/POST /api/v1/finance/payroll-rules`
- `POST /api/v1/finance/payroll-rules/{id}/submit-approval`
- `GET/POST /api/v1/finance/payroll-calculations`
- `POST /api/v1/finance/payroll-calculations/{id}/confirm`
- `GET /api/v1/finance/payroll`
- `GET /api/v1/admin/payroll-approvals`
- `POST /api/v1/admin/payroll-approvals/{id}/decision`
- `POST /api/v1/admin/payroll-recalculations`
- `GET /api/v1/admin/payroll`
- `GET /api/v1/plant/payroll`

## 数据不变量

1. 未批准规则永不执行。
2. 新规则默认不追溯历史。
3. 每次重算生成新批次和新结果，不更新旧结果。
4. 未确认批次不属于正式工资。
5. 工资查看范围由服务端身份确定，前端参数不能扩大权限。
