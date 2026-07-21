# PWA 移动生产接线验收记录

日期：2026-07-21
分支：`codex/low-token-ui-v2`
范围：Phase 1 原子电子提交，以及生产身份、API、Cookie 会话、IndexedDB/outbox、表单引擎、PWA 缓存和原型清理。

## 自动化结论

| 验收项 | 结果 | 证据 |
|---|---|---|
| 有效员工登录；无 token 响应 | 通过 | 持久凭据/会话 API 测试，HttpOnly/SameSite/CSRF 断言 |
| 只加载授权且已发布 Definition | 通过 | 移动 Definition API 与前端闭环测试 |
| SELF 服务端权威提交 | 通过 | subject 防伪、Definition 版本、字段白名单测试 |
| TEAM_LEADER_BATCH 同班组校验 | 通过 | 越班组提交返回 `SUBJECT_NOT_IN_TEAM` |
| 幂等重放只产生一张 Form | 通过 | 同键同载荷返回同一 Receipt；异载荷 409 |
| Form/Field/Audit/Receipt/Fact 原子性 | 通过 | UoW 故障注入与回滚集成测试 |
| 进入现有审核/导出主链 | 通过 | Form 状态为 NEEDS_REVIEW，电子事实与既有记录/导出集成测试 |
| 草稿刷新后恢复与人员隔离 | 通过 | IndexedDB storageKey 为 owner/device/localDraftId；页面只读本地草稿 |
| outbox 重放与错误分流 | 通过 | 共享 Promise、401 暂停、403/409/422 最终失败、网络/5xx 退避测试 |
| 私有响应不进入 SW 缓存 | 通过 | API、证据和下载路径 11 项 NetworkOnly 静态测试 |
| 公共设备退出清理 | 通过 | 停止同步、服务端 revoke、清 sessionMetadata/当前人员草稿、保留 outbox |
| 无试点身份/固定 PIN/双实现 | 通过 | 生产移动源扫描和旧模块/客户端不存在断言 |

完整自动检查结果：

- Python：452 passed；
- 前端：46 个 Vitest 文件，237 passed；
- Ruff：`app config tests` 通过；
- Mypy：`app config` 通过；
- TypeScript：web workspace 通过；
- Vite PWA 生产构建通过，生成 `dist/sw.js` 与 Workbox 文件。

## 明确降级与未接入能力

- 竹丝笼没有可靠生产 provider：`active-resources` 返回 503，页面显示暂不可填写；没有固定笼号或模拟库存。
- 桌面端仍使用既有本地完整权限模式；本验收只覆盖 `/api/v1/mobile` 的员工身份边界。
- 当前是本地单机技术基线，不代表已经完成 HTTPS、反向代理、多实例、500 人容量或灾备验收。

## 待人工真机验证

以下项目没有真实设备证据，状态均为**待人工验证**：

- Android Chrome / iOS Safari 安装与桌面图标；
- 360px 宽、横竖屏、软键盘和触控可用性；
- 现场弱网、完全断网、浏览器强退后恢复、重新联网补交；
- 公共设备 A 员工退出、保留 outbox、B 员工登录后的数据隔离；
- 有未提交 outbox 时更新提示只允许稍后，清空后激活新 Service Worker；
- 现场表单术语、班组关系、岗位授权与两张目标表字段签字；
- 可信 HTTPS、反向代理、备份恢复和故障演练。

未完成上述人工项目之前，不得把本记录表述为“已投产”或“真机全部通过”。
