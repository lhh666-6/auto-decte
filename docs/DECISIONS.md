# 技术决策记录

最后更新：2026-07-16

本文件只记录已经由本阶段代码、提交或回归修复体现的决定。未来设想仍以设计规范和 `NEXT_TASK.md` 为准。

## 本阶段新增的重要技术决策

### D-001：无登录本地模式拥有完整业务权限，认证模式保留角色矩阵

- 决定：默认使用 `APP_AUTH_MODE=local_full_access`。审计主体仍为 `local-operator`，角色仍为 `OPERATOR`，但本地单机模式放行全部业务权限；切换到 `APP_AUTH_MODE=authenticated` 后继续执行原有角色权限矩阵。
- 原因：当前产品尚无登录、身份切换和角色管理，最小权限默认身份会形成工作人员无法自行解除的业务死路；以独立运行模式放行可以满足本地实物验收，同时不删除未来认证所需的权限框架。
- 证据：`config/settings.py`、`app/api/dependencies_ds.py`、`app/modules/identity_access/policy_ds.py`、Task 1 定向权限与审计测试。

### D-002：模板库显示真实持久化数据，不在前端伪造模板

- 决定：四个企业模板通过组合根调用幂等 seed 安装为真实 `PUBLISHED` V1，模板库、预览、调优和打印均读取后端数据。
- 原因：前端假卡片无法参与 QR 分类、版本绑定、审计或导出映射，也会掩盖后端安装失败。
- 证据：`app/modules/templates/seed_templates_ds.py`、提交 `3ed353c`。

### D-003：发布模板不可编辑，调优必须克隆新版本

- 决定：只有草稿类状态可编辑；发布版本只读，调优创建带父版本关系的新草稿；退役保留历史版本和打印产物。
- 原因：已导入表单必须永久追溯到导入时的模板、坐标和规则，原地修改会破坏历史事实。
- 证据：`app/application/template_versions_ds.py`、`TemplateLibrary_ds.tsx`、`TemplateStudio_ds.tsx`。

### D-004：审核确认与领取下一张在同一事务中完成

- 决定：`confirm-and-claim-next` 同时验证权限、Lease、乐观版本和规则，写正式版本、审计、释放当前 Lease 并领取下一张。
- 原因：拆成多个请求会产生已确认但锁未释放、重复领取或并发覆盖窗口。
- 证据：`app/modules/review/facade_ds.py`、`app/api/routers/review_ds.py`、提交 `a20e295`。

### D-005：主数据采用稳定编码、乐观版本和逻辑停用

- 决定：员工、工单、产品和工序编码创建后不可修改；更新使用 revision/If-Match；删除改为停用，所有变更保留独立审计。
- 原因：历史表单和模板字段需要稳定引用；物理删除会造成不可追溯的悬空值。
- 证据：`app/modules/master_data/`、`alembic/versions/006_master_data_ds.py`、提交 `5b9de49`。

### D-006：只对原始图片执行 SHA-256 全局唯一

- 决定：`ORIGINAL_IMAGE` 保持全局唯一；校正图和字段裁切允许不同表单出现相同内容。
- 原因：空白或相同字段裁切很常见，全局去重派生证据会造成识别任务失败和半成品数据。
- 证据：`alembic/versions/005_original_evidence_dedup_ds.py`、`bd54ab3`。

### D-007：中断迁移的空版本表不视为已受 Alembic 管理

- 决定：只有 `alembic_version` 存在且包含非空版本号时才执行正式升级；空表按旧版自动建库兼容路径处理。
- 原因：SQLite DDL 非事务性，失败升级可能留下空版本表和已有业务表；仅检查表名会重复执行 001 建表并永久阻止启动。
- 证据：`app/infrastructure/database/migrations.py`、提交 `f050c7e`。

### D-008：内置 seed 冲突不得覆盖旧模板，也不得阻止应用启动

- 决定：严格 seed 安装函数继续整体拒绝同键同版本不同内容；应用组合根捕获冲突、记录警告、保留旧模板并继续启动。
- 原因：自动覆盖会破坏历史绑定；让可选 seed 冲突拖垮整个 API 又会阻断旧库升级。
- 证据：`app/modules/templates/seed_templates_ds.py`、`app/services/container.py`、提交 `f050c7e`。

### D-009：Web 与未来桌面壳共用同一 React Feature

- 决定：业务 Feature 只依赖 API Client、Shell Ports、共享状态和设计系统；浏览器页面不直接依赖 Tauri、本地路径或数据库。
- 原因：保持 Web 可运行，同时为 Tauri 封装、设备端口和 Windows 安装包保留演进路径。
- 证据：`frontend/apps/web/`、`frontend/packages/api-client/`、`frontend/packages/shell-ports/`。

### D-010：模块入口只存在于全局导航，审核队列只存在于工作台内部

- 决定：产品品牌不可点击；审核、模板、基础数据和导出只从全局一级导航进入。待确认表单类型、待核对和待重新拍照是审核工作台内部标签，不再与模块入口混排，也不设置“可导出”审核队列。
- 原因：模块导航和业务队列属于不同层级；重复页头、侧栏入口和返回按钮会制造多套导航语义，“可导出”则是导出模块的筛选结果而不是审核任务。
- 证据：`frontend/apps/web/src/app/AppShell.tsx`、`frontend/apps/web/src/app/router.tsx`、`frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`、Task 2 组件测试与浏览器路由验收。

### D-011：单表版面保持归一化坐标，物理规则和拼版使用毫米

- 决定：字段与静态元素继续以单表归一化坐标保存；纸张尺寸、最小填写尺寸、外边距、二维码安全区、拼版间距和承载纸容量按毫米计算。拼版是打印包配置，不改变单表模板键、版本和坐标。
- 原因：归一化坐标保持现有识别链兼容，毫米约束才能保证跨纸张尺寸的可填写、可打印和可裁切；把拼版坐标写回单表会破坏二维码和历史版本绑定。
- 证据：`app/domain/templates_ds.py`、`app/application/template_versions_ds.py`、Task 3 领域与发布前检查测试。

### D-012：识别候选、审核预填和正式确认是三种不同状态

- 决定：`RecognitionMode` 只决定是否以及怎样产生候选，`FillPolicy` 只决定候选是否进入最终填写值控件，正式记录仍必须经过审核确认；`PaperEntryMode` 独立描述纸面交互。姓名只能人工确认，自动计算没有 OCR 候选和可靠度阈值。
- 原因：把识别、预填和确认混成一个“自动”开关会让高可靠度候选绕过人工审核，也会让不识别或计算字段残留隐藏阈值。
- 证据：`app/domain/templates_ds.py`、`app/application/template_versions_ds.py`、Task 4 字段行为与发布前检查测试。

### D-013：新版模板 JSON 追加键，旧 JSON 读取时推导而不原地覆盖

- 决定：迁移 `008` 只追加模板版本静态元素和拼版列；字段行为继续扩展现有字段定义 JSON。缺少新键的旧字段按旧输入类型和识别引擎推导，只有后续编辑保存时才写完整新格式。仓储自身校验已持久化不可变版本，不能依赖调用方自觉。
- 原因：批量重写历史 JSON 会增加迁移失败和历史语义改变风险；读取兼容可以保留旧 V1，同时让新草稿使用明确模型。仓储防线可阻止脚本或适配器绕过领域对象修改发布事实。
- 证据：`alembic/versions/008_template_layout_behavior_ds.py`、`app/adapters/database/template_repository_ds.py`、Task 5 空库/旧库和不可变仓储测试。

### D-014：API 以结构化纸张扩展，旧 page_size 只作为兼容入口

- 决定：新版调用使用结构化 `page` 和严格 TypeScript 判别联合表达标准/自定义纸张；旧客户端仍可发送 `page_size: A4/A5`。模板详情始终返回完整物理版面和字段行为，不能用 `unknown` 或任意字典代替契约。
- 原因：仅扩展 `page_size` 字符串无法安全携带毫米尺寸、方向和 DPI；直接删除旧参数又会中断现有模板中心。双入口、单一完整响应可以渐进迁移且保持类型安全。
- 证据：`app/api/routers/templates_ds.py`、`frontend/packages/api-client/src/templates_ds.ts`、Task 6 API 与类型测试。

### D-015：字段新增是独立事务，编辑器交互以毫米约束但继续保存归一化坐标

- 决定：添加字段使用独立对话框和新内部草稿，唯一键校验、重复提交锁和失败回滚在客户端请求边界完成；移动、缩放和对齐以 1 mm 网格工作，持久化仍转换为单表归一化坐标。结构操作与几何操作分别保留撤销/重做历史。发布版只读，只能克隆后修改。
- 原因：复用选中字段状态会造成误覆盖、重复创建和失败后画布漂移；直接把毫米值写入现有字段坐标又会破坏识别与历史模板兼容。独立事务与毫米交互层可以同时保证安全编辑和既有后端契约。
- 证据：`frontend/apps/web/src/TemplateStudio_ds.tsx`、`TemplateCanvasEditor_ds.tsx`、`FieldInspector_ds.tsx`、`template-studio-model.ts` 及 Task 7 组件/模型测试和浏览器验收。

### D-016：三类母版只复用结构，十张成品模板各自保存明确业务语义

- 决定：计时、等级计件、固定生产明细三类母版用于复用版面规则，但只发布十张带明确中文标题、字段和结构清单的车间成品模板。四张旧通用 seed 继续保留用于历史兼容；新安装共 14 个 V1。seed 内容指纹包含静态元素和拼版，并将等价的整数/浮点毫米值规范化后比较，真正同键同版本冲突仍拒绝覆盖。
- 原因：发布抽象母版或使用编号明细占位会把业务判断推给现场人员；删除旧 V1 又会破坏历史表单引用。结构复用与成品语义分离，可以兼顾实际填写、自动测试和历史不变量。
- 证据：`app/modules/templates/payroll_profiles_ds.py`、`app/modules/templates/seed_templates_ds.py`、Task 8 模板结构、物理预检、幂等和冲突测试。

### D-017：二维码安全区与实际符号分离，拼版槽位必须独立渲染

- 决定：继续为模板码和实例码各保留 29 mm 安全区，但实际二维码使用带四模块静区的 18 mm 符号并在安全区内下对齐，以避开右上 12 mm 定位标记。拼版不复制单张位图，每个槽位重新渲染，并在给出打印批次时使用递增实例序号。发布 API 必须先解析中文字体，再改变版本状态。
- 原因：把二维码铺满安全区会被右上定位标记覆盖；复制位图会让两张纸共享实例身份；先发布后渲染则会在字体缺失时留下没有可打印产物的发布版本。
- 证据：`app/adapters/templates/print_renderer_ds.py`、`app/api/routers/templates_ds.py`、Task 9 二维码多码解码、字体失败状态和打印产物测试。

### D-018：多码分类只接受可校验身份，任何歧义都转人工并审计

- 决定：导入识别读取全部二维码并分别校验 `IFD` 模板身份与 `SHEET` 实例身份；同一小表两者同时有效时以实例码作为分类来源、以模板码解析精确不可变版本。实例码本身不携带模板键，不能单独用于猜测模板。出现多个不同模板或实例身份时保持原模板引用，进入待分类并写 `CLASSIFICATION_CONFLICT` 审计。
- 原因：单码 API 在有两个二维码时可能读到任意一个；把实例序号当模板映射或从版面猜测会形成静默错分。保留全部冲突引用并人工处理，才能维持工业表单的精确版本和审计边界。
- 证据：`app/adapters/recognition/opencv.py`、`app/application/recognize_forms.py`、Task 10 十模板 PNG、两联裁切、实例优先和冲突测试。

### D-019：字段行为由模板契约驱动，三类审核队列共享图片证据骨架

- 决定：工作台字段响应显式携带纸面填写、识别、审核填入和必须人工确认行为；前端据此决定是否展示候选与可靠度，而不是只根据历史识别引擎猜测。待分类、待核对和待重新拍照共享左侧图片证据、右侧业务处理的双栏结构；姓名字段必须展示原图裁片并由人员确认。
- 原因：旧候选可能在模板改为不识别后仍存在，如果继续显示会误导审核人员；分类队列脱离原图也会迫使人员在没有证据的情况下选模板。把行为纳入稳定接口并统一证据骨架，可以让不同队列保持一致且不伪造自动识别能力。
- 证据：`app/api/routers/workbench_ds.py`、`frontend/apps/web/src/workbench/field-behavior.ts`、`ClassificationStage.tsx`、`FieldDetailPanel.tsx` 及 Task 11 API/组件测试和 Edge 冒烟。

### D-020：姓名确认是显式提交事实，工号状态由有效员工主数据决定

- 决定：姓名字段除了模板的 `requires_manual_confirmation` 标记外，审核提交还必须携带已人工确认字段键；后端在写入记录前独立校验。工号匹配只接受有效员工主数据，未知或停用工号必须人工选择或修正。工作台按稳定的四类业务角色分组，不从候选可靠度推断人员身份。
- 原因：仅在前端显示警告可被旧客户端或直接 API 调用绕过；仅凭高可靠度候选也不能证明姓名经过人员核对。员工有效状态和显式确认声明进入提交边界后，才能阻止自动放行并保留责任人、时间和原因。
- 证据：`app/modules/review/facade_ds.py`、`app/api/schemas/review_ds.py`、`frontend/apps/web/src/workbench/FieldReviewTable.tsx`、`ReviewWorkbenchPage.tsx` 及 Task 12 审核工作流、主数据和组件测试。

### D-021：导出检查是生成前快照，导出记录不属于操作步骤

- 决定：工作人员按“选择数据 → 检查数据 → 生成并下载”完成一次导出；检查结果只在主动检查后出现，任何筛选或导出类型变化都废弃旧结果并要求重新检查。生成任务的进度、失败和即时下载留在第三步，历史导出记录作为独立区域展示；技术标识只在主动展开的追溯详情中提供。
- 原因：把历史记录编号为第四步会混淆当前操作和既有产物，筛选变化后保留旧预览又可能生成与界面条件不一致的 Excel。三步快照约束可以维持现有后端不可变批次语义，同时让失败恢复和下载入口更接近工作人员当前动作。
- 证据：`frontend/apps/web/src/ExportCenter_ds.tsx`、`frontend/apps/web/src/export-center.test.tsx` 及 Task 13 导出 API/组件测试、TypeScript 和生产构建。

### D-022：稳定 Excel 映射通过新模板版本发布，不改写已发布 V1

- 决定：十个真实工资表保留原 V1，并分别发布 V2 导出映射；V2 统一将人员、考评、事实说明和签字写入“工资主记录”，将岗位字段写入“业务明细”，两表以批次、表单和记录版本关联。映射快照按不可变模板字段顺序生成，中文业务列和 Excel 原生类型随批次固化。
- 原因：直接改写 V1 的导出目标会改变历史表单的导出事实并触发种子内容冲突；按 V2 追加可以让已有数据库安全升级，同时让固定生产明细形成可追溯的主记录/明细行结构，并保持四个历史通用模板原样可导出。
- 证据：`app/modules/templates/payroll_profiles_ds.py`、`app/modules/templates/seed_templates_ds.py`、`app/application/export_forms.py`、`tests/integration/test_payroll_xlsx_export_ds.py` 及 Task 14 的 41 项定向测试和静态检查。

### D-023：工作人员主界面只展示业务语义，技术原值收进追溯详情

- 决定：任务状态通过集中字典转换为中文短文案、说明和下一步动作；审核 Lease 对工作人员表达为“开始审核 / 你正在审核”。模板 ID、任务 ID、后端状态码和步骤码仍保留，但只在主动展开的追溯详情中展示。
- 原因：后端代码和 Lease 实现术语无法直接指导现场人员操作，但完全删除又会损害故障排查和审计。主界面与追溯层分离可以同时保证可用性和可追溯性。
- 证据：`frontend/apps/web/src/ui/business-language.ts`、`frontend/apps/web/src/ui/TraceDetails.tsx`、审核工作台、识别进度、模板中心和导出中心组件，以及 Task 15 的 74 项定向前端测试。

### D-024：打印与透视校正共享毫米几何，高分辨率二维码只做像素回退

- 决定：方向标记恢复位置由 5 mm 打印边距、12 mm 标记和模板 `canonical_dpi` 确定，不再使用与打印器无关的经验像素值。二维码读取在原图失败时可使用灰度均衡、二值化和降采样，但仍只接受校验通过的码值，不从表格版面猜测模板。
- 原因：打印标记与校正目标不一致会使视觉上可用的照片产生系统性字段偏移；高分辨率照片又可能超出 OpenCV 在单一尺度下的稳定识别区间。物理契约与多尺度像素回退可以解决两者，且不放宽精确版本安全边界。
- 证据：`app/adapters/recognition/opencv.py`、`app/application/recognize_forms.py`、`tests/unit/test_image_pipeline.py`、`tests/integration/test_paper_template_acceptance_ds.py` 及 [Task 16 验收记录](acceptance/PAPER_TEMPLATE_ACCEPTANCE.md)。

## 已否决方案及原因

| 已否决方案 | 原因 |
|---|---|
| 把本地操作员角色直接改成 ADMIN | 会混淆审计身份与角色语义；现在使用独立 `local_full_access` 模式，认证模式仍按角色矩阵授权。 |
| 在 React 中硬编码四个模板卡片 | 无法参与真实模板版本、QR 分类、打印、审计和导出映射。 |
| 发布后原地修改模板字段或坐标 | 会使历史表单无法重现导入时的识别配置，破坏审计链。 |
| 物理删除已发布模板或主数据 | 会破坏历史引用和追溯；使用退役/停用替代。 |
| 对全部证据文件应用 SHA 全局唯一 | 派生裁切可能天然相同，会导致合法任务冲突和半成品。 |
| QR 失败后自动猜测最相似模板 | 工业数据静默错分风险不可接受；必须进入待分类并记录人工选择审计。 |
| 将空 `alembic_version` 表直接视为当前迁移库 | 中断升级后会从 001 重建已有表并导致启动失败。 |
| 内置 seed 冲突时自动覆盖旧 V1 | 旧表单可能绑定该版本，覆盖会改变历史事实。 |
| 内置 seed 冲突时让整个应用退出 | seed 是可选初始化，不应阻断旧业务库访问；现在保留旧模板并告警。 |
| 继续以同步 Streamlit 按钮作为产品化导出中心 | 缺少 API 权限、任务进度、受控下载、不可变快照和 React/Web-Tauri 共用能力。 |
| 浏览器直接读取服务器绝对路径或数据库对象 | 泄露内部存储结构，且无法迁移到 Web/Tauri 双壳和远程部署。 |

## 下一阶段必须延续的约束

- 导出中心先建立后端契约、持久化任务和安全边界，再接 React 页面。
- 旧导出、旧模板和旧审计不可覆盖。
- 新迁移只能追加，不修改 `001`–`006`。
- 本地完整权限不得通过把默认角色临时升级成 ADMIN 实现；必须由 `APP_AUTH_MODE` 明确控制，并保留认证模式的角色边界。
